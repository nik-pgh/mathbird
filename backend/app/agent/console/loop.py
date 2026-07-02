"""Interactive console read/eval/print loop for local agent sessions."""

from __future__ import annotations

import asyncio
import logging

from app.agent.console.identity import (
    lookup_doc_filename,
    lookup_user_email,
    resolve_local_identity,
)
from app.agent.console.render import render_turn_panel
from app.agent.console.runtime import local_text_job
from app.agent.console.turn import await_turn_grading, run_text_turn
from app.agent.console.ui import (
    print_banner,
    print_dim,
    print_latest_assistant_from_history,
    print_turn_divider,
    render_run_events,
)
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


async def run_console(*, show_context: bool = False) -> None:
    settings = get_settings()
    logging.getLogger("livekit.agents").setLevel(logging.WARNING)

    async with local_text_job() as ctx:
        room = ctx.room
        user_id, active_doc_id = await resolve_local_identity(settings)
        doc_filename = await lookup_doc_filename(active_doc_id)
        user_email = lookup_user_email(user_id)

        bundle = await build_session_bundle(
            room=room,
            settings=settings,
            user_id=user_id,
            active_doc_id=active_doc_id,
            text_only=True,
        )
        engine = bundle.session_data.progress_engine

        print_banner(
            doc_id=active_doc_id,
            user_id=user_id,
            doc_filename=doc_filename,
            user_email=user_email,
            settings=settings,
        )

        # No room= — avoids RoomIO on an unconnected fake room (local_participant errors).
        await bundle.session.start(agent=bundle.agent, record=False)

        try:
            has_progress = engine is not None
            await send_initial_greeting(bundle.session, has_progress=has_progress)
            print_latest_assistant_from_history(bundle.session.history)

            turn_number = 0
            while True:
                user_text = await _read_user_input()
                if user_text is None or _is_quit_command(user_text):
                    print_dim("\n[dim]Goodbye.[/dim]")
                    break
                if not user_text:
                    continue

                turn_number += 1
                result = await run_text_turn(bundle.session, bundle.agent, user_text)
                await result.run
                await await_turn_grading(result)

                if show_context:
                    render_turn_panel(
                        turn_number=turn_number,
                        user_text=user_text,
                        context=result.snapshot,
                        run=result.run,
                        engine=engine,
                    )
                else:
                    render_run_events(result.run.events, skip_user=True)

                print_turn_divider()
        finally:
            await bundle.listener.aclose()
            await bundle.session.aclose()
            await room.disconnect()
