"""Interactive text console with readable tutor output.

Usage (from ``backend/``)::

    uv run python -m scripts.agent_console

Type ``exit`` or ``quit`` (or press Ctrl+D) to leave cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.agent.console.identity import resolve_local_identity
from app.agent.console.runtime import local_text_job
from app.agent.console.ui import (
    print_banner,
    print_dim,
    print_latest_assistant_from_history,
    print_turn_divider,
    print_user_message,
    render_run_events,
)
from app.agent.providers import ensure_livekit_plugins_registered
from app.agent.session_factory import build_session_bundle, send_initial_greeting
from app.config import get_settings

_QUIT_COMMANDS = frozenset({"exit", "quit"})


def _is_quit_command(text: str) -> bool:
    return text.lower() in _QUIT_COMMANDS


async def _read_user_input() -> str | None:
    loop = asyncio.get_running_loop()
    try:
        line = await loop.run_in_executor(None, lambda: input("\n❯ "))
    except (EOFError, KeyboardInterrupt):
        return None
    return line.strip()


async def run_console() -> None:
    settings = get_settings()
    logging.getLogger("livekit.agents").setLevel(logging.WARNING)

    async with local_text_job() as ctx:
        room = ctx.room
        user_id, active_doc_id = await resolve_local_identity(settings)

        bundle = await build_session_bundle(
            room=room,
            settings=settings,
            user_id=user_id,
            active_doc_id=active_doc_id,
            text_only=True,
        )

        print_banner(doc_id=active_doc_id, user_id=user_id)

        # No room= — avoids RoomIO on an unconnected fake room (local_participant errors).
        await bundle.session.start(agent=bundle.agent, record=False)

        try:
            has_progress = bundle.session_data.progress_engine is not None
            await send_initial_greeting(bundle.session, has_progress=has_progress)
            print_latest_assistant_from_history(bundle.session.history)

            while True:
                user_text = await _read_user_input()
                if user_text is None or _is_quit_command(user_text):
                    print_dim("\n[dim]Goodbye.[/dim]")
                    break
                if not user_text:
                    continue

                print_user_message(user_text)
                run = bundle.session.run(user_input=user_text)
                await run
                render_run_events(run.events, skip_user=True)
                print_turn_divider()
        finally:
            await bundle.listener.aclose()
            await bundle.session.aclose()
            await room.disconnect()


def main() -> int:
    ensure_livekit_plugins_registered()
    try:
        asyncio.run(run_console())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
