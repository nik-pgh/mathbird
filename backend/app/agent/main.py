"""LiveKit agent entrypoint.

Run locally:
    uv run python -m app.agent.main dev

Connects to LiveKit Cloud using ``LIVEKIT_URL`` / ``LIVEKIT_API_KEY`` /
``LIVEKIT_API_SECRET``. When a participant joins a room, the worker spawns an
``Agent`` session for that room.
"""

# ruff: noqa: I001
from __future__ import annotations

import logging

# Phoenix instrumentation must run inside the per-room job process, not only
# in the worker parent. Keep this import ahead of provider construction so
# entrypoint can patch OpenAI/LlamaIndex before those clients are built.
from app.observability import setup_phoenix

import json  # noqa: E402

from livekit.agents import (  # noqa: E402
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)

from app.agent.providers import build_llm, build_stt, build_tts, build_vad  # noqa: E402
from app.agent.tools import build_function_tools  # noqa: E402
from app.agent.whiteboard import (  # noqa: E402
    BoardCache,
    BoardState,
    SessionData,
    get_board_extractor,
    get_board_reader,
    install_user_board_listener,
)
from app.agent.whiteboard_agent import WhiteboardAgent  # noqa: E402
from app.config import get_settings  # noqa: E402

logger = logging.getLogger("mathbird.agent")


def _parse_participant_metadata(metadata: str | None) -> tuple[str | None, str | None]:
    if not metadata:
        return None, None
    try:
        payload = json.loads(metadata)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    user_id = payload.get("user_id")
    active_doc_id = payload.get("active_doc_id")
    return (
        user_id if isinstance(user_id, str) and user_id else None,
        active_doc_id if isinstance(active_doc_id, str) and active_doc_id else None,
    )


async def _load_progress_engine(
    user_id: str,
    doc_id: str,
):
    from datetime import UTC, datetime

    from app.progress import ProgressEngine, ProgressState, get_progress_store
    from app.storage import get_storage
    from app.syllabus import load_syllabus

    storage = get_storage()
    syllabus = await load_syllabus(storage, doc_id)
    if syllabus is None:
        return None, None

    store = get_progress_store(storage)
    state = await store.load(user_id, doc_id)
    if state is None:
        state = ProgressState(
            user_id=user_id,
            doc_id=doc_id,
            updated_at=datetime.now(UTC).isoformat(),
        )
    engine = ProgressEngine(syllabus=syllabus, state=state)
    return syllabus, engine


def _parse_active_doc_id(metadata: str | None) -> str | None:
    _user_id, active_doc_id = _parse_participant_metadata(metadata)
    return active_doc_id


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit worker once per room."""
    setup_phoenix()
    settings = get_settings()
    logger.info(
        "agent joining room=%s providers=stt:%s llm:%s tts:%s vad:%s"
        " board_reader=%s board_extractor=%s",
        ctx.room.name,
        settings.stt_provider,
        settings.llm_provider,
        settings.tts_provider,
        settings.vad_provider,
        settings.board_reader,
        settings.board_extractor,
    )

    await ctx.connect()

    # Install the user-board data-channel listener BEFORE awaiting the
    # participant. ``wait_for_participant`` can return after the user has
    # already started publishing snapshots, so registering ``data_received``
    # any later would drop early packets and the AiBoard would never see
    # the student's first strokes.
    board_state = BoardState()
    board_cache = BoardCache()
    board_reader = get_board_reader()
    board_extractor = get_board_extractor()
    listener = install_user_board_listener(
        room=ctx.room,
        state=board_state,
        reader=board_reader,
        interval=settings.board_reader_interval_seconds,
    )
    ctx.add_shutdown_callback(listener.aclose)

    # Now read active_doc_id from the joining participant's metadata. The
    # token route writes ``{"active_doc_id": "..."}`` into it when the
    # frontend supplies one. If no participant arrives or the metadata is
    # missing, we proceed without a doc filter (search_documents falls back
    # to all docs).
    active_doc_id: str | None = None
    user_id: str | None = None
    syllabus = None
    progress_engine = None
    try:
        participant = await ctx.wait_for_participant()
        user_id, active_doc_id = _parse_participant_metadata(participant.metadata)
    except Exception:
        logger.exception("Failed to read participant metadata; proceeding without doc filter.")

    if user_id and active_doc_id:
        try:
            syllabus, progress_engine = await _load_progress_engine(user_id, active_doc_id)
        except Exception:
            logger.exception(
                "Failed to load progress for user_id=%s doc_id=%s",
                user_id,
                active_doc_id,
            )

    session_data = SessionData(
        board_state=board_state,
        board_cache=board_cache,
        active_doc_id=active_doc_id,
        user_id=user_id,
        syllabus=syllabus,
        progress_engine=progress_engine,
    )

    session = AgentSession(
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=build_vad(settings),
        userdata=session_data,
    )

    agent = WhiteboardAgent(
        instructions=settings.agent_instructions,
        tools=build_function_tools(include_progress=progress_engine is not None),
        board_state=board_state,
        board_cache=board_cache,
        extractor=board_extractor,
        progress_engine=progress_engine,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    if progress_engine is not None:
        try:
            from app.progress.publisher import publish_session_progress

            await publish_session_progress(ctx.room, progress_engine.snapshot_update())
        except Exception:
            logger.exception("Failed to publish initial session progress snapshot")

    if progress_engine is not None:
        await session.generate_reply(
            instructions=(
                "Greet briefly. If session progress shows a current focus, offer to "
                "continue there or jump to another problem."
            )
        )
    else:
        await session.generate_reply(
            instructions="Greet the user briefly and ask how you can help."
        )


def main() -> None:
    """CLI entrypoint. ``dev`` runs the worker locally against LiveKit Cloud."""
    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.livekit_url or None,
            api_key=settings.livekit_api_key or None,
            api_secret=settings.livekit_api_secret or None,
        )
    )


if __name__ == "__main__":
    main()
