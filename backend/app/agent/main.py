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
    BoardState,
    get_board_reader,
    install_user_board_listener,
)
from app.agent.whiteboard_agent import WhiteboardAgent  # noqa: E402
from app.config import get_settings  # noqa: E402

logger = logging.getLogger("mathbird.agent")


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit worker once per room."""
    settings = get_settings()
    logger.info(
        "agent joining room=%s providers=stt:%s llm:%s tts:%s vad:%s board_reader=%s",
        ctx.room.name,
        settings.stt_provider,
        settings.llm_provider,
        settings.tts_provider,
        settings.vad_provider,
        settings.board_reader,
    )

    await ctx.connect()

    # Whiteboard wiring — must come before the session starts so the listener
    # is in place by the time the user's first stroke arrives. ``BoardState``
    # rides on ``AgentSession.userdata`` so the function tools can reach it
    # via ``ctx.session.userdata``.
    board_state = BoardState()
    board_reader = get_board_reader()
    listener = install_user_board_listener(
        room=ctx.room,
        state=board_state,
        reader=board_reader,
        interval=settings.board_reader_interval_seconds,
    )

    session = AgentSession(
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=build_vad(settings),
        userdata=board_state,
    )

    agent = WhiteboardAgent(
        instructions=settings.agent_instructions,
        tools=build_function_tools(),
        board_state=board_state,
    )

    try:
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(),
        )

        # Optional opening greeting — comment out to stay silent until spoken to.
        await session.generate_reply(
            instructions="Greet the user briefly and ask how you can help."
        )
    finally:
        await listener.aclose()


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
