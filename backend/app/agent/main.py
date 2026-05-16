"""LiveKit agent entrypoint.

Run locally:
    uv run python -m app.agent.main dev

Connects to LiveKit Cloud using ``LIVEKIT_URL`` / ``LIVEKIT_API_KEY`` /
``LIVEKIT_API_SECRET``. When a participant joins a room, the worker spawns an
``Agent`` session for that room.
"""

from __future__ import annotations

import logging

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)

from app.agent.providers import build_llm, build_stt, build_tts, build_vad
from app.agent.tools import build_function_tools
from app.config import get_settings

logger = logging.getLogger("mathbird.agent")


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit worker once per room."""
    settings = get_settings()
    logger.info(
        "agent joining room=%s providers=stt:%s llm:%s tts:%s vad:%s",
        ctx.room.name,
        settings.stt_provider,
        settings.llm_provider,
        settings.tts_provider,
        settings.vad_provider,
    )

    # Wait until a human participant is in the room before doing setup work.
    await ctx.connect()

    session = AgentSession(
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=build_vad(settings),
    )

    agent = Agent(
        instructions=settings.agent_instructions,
        tools=build_function_tools(),
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    # Optional opening greeting — comment out to stay silent until spoken to.
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
