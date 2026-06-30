"""LiveKit agent entrypoint.

Run locally:
    uv run python -m app.agent.main dev

Interactive text console (recommended — readable tutor output):
    uv run python -m scripts.agent_console

Legacy LiveKit console (debug logs may appear):
    uv run python -m app.agent.main console --text

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

from livekit.agents import (  # noqa: E402
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)

from app.agent.providers.register import ensure_livekit_plugins_registered
from app.agent.session_factory import (  # noqa: E402
    build_session_bundle,
    resolve_session_identity,
    send_initial_greeting,
)
from app.config import get_settings  # noqa: E402

logger = logging.getLogger("mathbird.agent")


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

    if ctx.is_fake_job():
        logging.getLogger("livekit.agents").setLevel(logging.WARNING)

    user_id, active_doc_id = await resolve_session_identity(ctx, settings)
    bundle = await build_session_bundle(
        room=ctx.room,
        settings=settings,
        user_id=user_id,
        active_doc_id=active_doc_id,
    )
    ctx.add_shutdown_callback(bundle.listener.aclose)

    await bundle.session.start(
        agent=bundle.agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    progress_engine = bundle.session_data.progress_engine
    if progress_engine is not None:
        try:
            from app.progress.publisher import publish_session_progress

            await publish_session_progress(ctx.room, progress_engine.snapshot_update())
        except Exception:
            logger.exception("Failed to publish initial session progress snapshot")

    await send_initial_greeting(bundle.session, has_progress=progress_engine is not None)

    if ctx.is_fake_job():
        from app.agent.console.ui import print_banner, print_latest_assistant_from_history

        print_banner(doc_id=active_doc_id, user_id=user_id)
        print_latest_assistant_from_history(bundle.session.history)


def main() -> None:
    """CLI entrypoint. ``dev`` runs the worker locally against LiveKit Cloud."""
    ensure_livekit_plugins_registered()
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
