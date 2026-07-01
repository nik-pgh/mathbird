"""Inspection helpers — show the per-turn LLM nudge and progress state.

Shared by the scripted simulator (``scripts.simulate_conversation``) and the
interactive console (``scripts.agent_console``) so both display the *exact*
string injected into the LLM each turn, with no parallel rendering that could
drift from the production hook in :mod:`app.agent.whiteboard_agent`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from livekit.agents.voice.run_result import RunEvent

    from app.agent.whiteboard import SessionData
    from app.progress.engine import ProgressEngine


def assistant_reply(events: list[RunEvent]) -> str:
    """Concatenate assistant message text from a turn's ``RunResult`` events."""
    parts: list[str] = []
    for event in events:
        if event.type != "message" or event.item.role != "assistant":
            continue
        parts.append(event.item.text_content)
    return "\n".join(parts)


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(f"{prefix}{line}" if line else line for line in text.splitlines())


def print_llm_context(session_data: SessionData, engine: ProgressEngine | None) -> None:
    """The exact nudge the LLM is about to see this turn.

    ``ProgressEngine.format_injection()`` returns the verbatim string the
    per-turn hook adds as a system message — calling it *before*
    ``session.run()`` reproduces that nudge from the engine's
    end-of-previous-turn state with zero drift.
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
    state = engine.state
    summary = engine.summary()
    focus = state.focus
    focus_node = (focus.problem_id or focus.concept_id) if focus is not None else None
    if focus_node is not None:
        level = engine.effective_level(focus_node)
        print(f"  focus: {focus_node} ({level})", flush=True)
    else:
        print("  focus: (none yet)", flush=True)
    print(
        f"  mastered: {summary.mastered}/{summary.total} · in progress: {summary.in_progress}",
        flush=True,
    )

    rec = engine.recommend()
    print(f"  recommend [{rec.intent}]: {rec.directive}", flush=True)

    touched: list[str] = []
    for node_id, node in state.nodes.items():
        level = engine.effective_level(node_id)
        bits: list[str] = []
        if level != "not_started":
            bits.append(level)
        if node.hints_given:
            bits.append(f"hints={node.hints_given}")
        if node.misconceptions:
            bits.append(f"misconceptions={node.misconceptions}")
        if bits:
            touched.append(f"{node_id}: {' / '.join(bits)}")
    if touched:
        print("  nodes:", flush=True)
        for line in touched:
            print(f"    - {line}", flush=True)
