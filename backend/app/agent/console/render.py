"""Rich turn panels for the interactive console (-c mode)."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from app.agent.console.ui import _summarize_tool_args, _truncate
from app.agent.turn_context.types import InjectionKind, TurnContextSnapshot

if TYPE_CHECKING:
    from livekit.agents.voice.run_result import RunEvent, RunResult

    from app.progress.engine import ProgressEngine

_console = Console(highlight=False)

_KIND_EMOJI: dict[InjectionKind, str] = {
    "board": "🖊",
    "progress": "📊",
    "textbook": "📖",
    "other": "📄",
}


def assistant_reply(events: list[RunEvent]) -> str:
    """Concatenate assistant message text from a turn's ``RunResult`` events."""
    parts: list[str] = []
    for event in events:
        if event.type != "message" or event.item.role != "assistant":
            continue
        text = event.item.text_content
        if text:
            parts.append(text)
    return "\n".join(parts)


def format_progress_lines(engine: ProgressEngine) -> list[str]:
    """Engine state after the turn — focus, summary, recommendation, touched nodes."""
    state = engine.state
    summary = engine.summary()
    focus = state.focus
    focus_node = (focus.problem_id or focus.concept_id) if focus is not None else None
    if focus_node is not None:
        level = engine.effective_level(focus_node)
        lines = [f"focus: {focus_node} ({level})"]
    else:
        lines = ["focus: (none yet)"]
    lines.append(
        f"mastered: {summary.mastered}/{summary.total} · in progress: {summary.in_progress}"
    )

    rec = engine.recommend()
    lines.append(f"recommend [{rec.intent}]: {rec.directive}")

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
        lines.append("nodes:")
        lines.extend(f"  - {line}" for line in touched)
    return lines


def render_turn_panel(
    *,
    turn_number: int,
    user_text: str,
    context: TurnContextSnapshot,
    run: RunResult,
    engine: ProgressEngine | None,
) -> None:
    """Render one Rich panel summarizing a single console turn."""
    lines: list[str] = []

    lines.append("[bold]👤 You[/bold]")
    body = textwrap.fill(user_text.strip(), width=_console.width - 6, subsequent_indent="  ")
    for line in body.splitlines():
        lines.append(f"  {line}")
    lines.append("")

    lines.append("[bold]📥 Injected context[/bold]")
    if not context.injections:
        lines.append("  [dim](none)[/dim]")
    else:
        for block in context.injections:
            emoji = _KIND_EMOJI[block.kind]
            lines.append(f"  {emoji} [dim]{block.kind}[/dim]")
            for content_line in block.content.splitlines():
                lines.append(f"    {content_line}" if content_line else "")
    lines.append("")

    lines.append("[bold]🔧 Tools[/bold]")
    tool_lines = _format_tool_lines(run.events)
    if tool_lines:
        lines.extend(tool_lines)
    else:
        lines.append("  [dim](none this turn)[/dim]")
    lines.append("")

    lines.append("[bold]🎓 Tutor[/bold]")
    reply = assistant_reply(run.events)
    if reply.strip():
        wrapped = textwrap.fill(reply.strip(), width=_console.width - 6, subsequent_indent="  ")
        for line in wrapped.splitlines():
            lines.append(f"  {line}")
    else:
        lines.append("  [dim](empty)[/dim]")
    lines.append("")

    lines.append("[bold]📈 Progress after grader[/bold]")
    if engine is None:
        lines.append("  [dim](no engine — progression tracking off)[/dim]")
    else:
        for line in format_progress_lines(engine):
            lines.append(f"  {line}")

    _console.print()
    _console.print(
        Panel(
            "\n".join(lines),
            title=f"Turn {turn_number}",
            border_style="bright_blue",
            padding=(0, 1),
        )
    )
    _console.print()


def _format_tool_lines(events: list[RunEvent]) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.type == "function_call":
            name = event.item.name
            arguments = event.item.arguments or ""
            summary = _summarize_tool_args(name, arguments)
            lines.append(
                f"  [dim]⎿[/dim] [bold magenta]{name}[/bold magenta][dim]({summary})[/dim]"
            )
        elif event.type == "function_call_output":
            name = event.item.name
            output = event.item.output or ""
            is_error = bool(event.item.is_error)
            style = "red" if is_error else "dim"
            preview = _truncate(output.replace("\n", " "), 100)
            lines.append(f"  [dim]↳[/dim] [{style}]{name}: {preview}[/{style}]")
    return lines
