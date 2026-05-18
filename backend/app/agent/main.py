"""LiveKit agent entrypoint.

Run locally:
    uv run python -m app.agent.main dev

Connects to LiveKit Cloud using ``LIVEKIT_URL`` / ``LIVEKIT_API_KEY`` /
``LIVEKIT_API_SECRET``. When a participant joins a room, the worker spawns an
``Agent`` session for that room.
"""

from __future__ import annotations

import logging

# Phoenix instrumentation must patch the OpenAI/LlamaIndex client classes
# BEFORE livekit.plugins.openai imports them, otherwise livekit captures
# unpatched method references and the LLM/RAG calls bypass tracing. Keep
# this import + call at the very top of the module, ahead of any livekit
# or providers imports.
from app.observability import setup_phoenix

setup_phoenix()

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


def _parse_active_doc_id(metadata: str | None) -> str | None:
    if not metadata:
        return None
    try:
        payload = json.loads(metadata)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    val = payload.get("active_doc_id")
    return val if isinstance(val, str) and val else None


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit worker once per room."""
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
    try:
        participant = await ctx.wait_for_participant()
        active_doc_id = _parse_active_doc_id(participant.metadata)
    except Exception:
        logger.exception("Failed to read participant metadata; proceeding without doc filter.")

    session_data = SessionData(
        board_state=board_state,
        board_cache=board_cache,
        active_doc_id=active_doc_id,
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
        tools=build_function_tools(),
        board_state=board_state,
        board_cache=board_cache,
        extractor=board_extractor,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

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
