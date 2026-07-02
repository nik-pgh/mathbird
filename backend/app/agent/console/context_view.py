"""Inspection helpers — show the per-turn LLM nudge and progress state.

Shared by the scripted simulator (``scripts.simulate_conversation``) and the
interactive console (``scripts.agent_console``) so both display the *exact*
string injected into the LLM each turn, with no parallel rendering that could
drift from the production hook in :mod:`app.agent.whiteboard_agent`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.console.render import format_progress_lines

if TYPE_CHECKING:
    from app.agent.whiteboard import SessionData
    from app.progress.engine import ProgressEngine


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(f"{prefix}{line}" if line else line for line in text.splitlines())


def print_llm_context(session_data: SessionData, engine: ProgressEngine | None) -> None:
    """The per-turn nudge injected via ``on_user_turn_completed``.

    Shows board state plus ``ProgressEngine.format_injection()`` from the
    engine's current state. In ``agent_console`` / ``simulate_conversation``,
    call this *after* the previous turn's ``run_text_turn`` (which runs the
    hook and grader) so focus and recommendations reflect grading.
    """
    board = session_data.board_state
    if board.refreshed_at is None:
        board_block = "(no reading yet)"
    elif board.is_blank:
        age = board.age_seconds()
        age_str = f"{age:.0f}s ago" if age is not None else "just now"
        board_block = f"(blank, refreshed {age_str})"
    else:
        age = board.age_seconds()
        age_str = f"{age:.0f}s ago" if age is not None else "just now"
        board_block = f"(refreshed {age_str})\n{board.user_text}"
    print(f"  board: {board_block}", flush=True)

    if engine is None:
        print("  progress: (no engine — progression tracking off)", flush=True)
        return
    print("  " + _indent(engine.format_injection()).lstrip(), flush=True)


def print_progress_snapshot(engine: ProgressEngine) -> None:
    """Engine state after the turn — focus, summary, recommendation, touched nodes."""
    for line in format_progress_lines(engine):
        print(f"  {line}", flush=True)
