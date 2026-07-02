"""Terminal formatting for interactive agent sessions (console / simulations)."""

from __future__ import annotations

import json
import textwrap
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

if TYPE_CHECKING:
    from livekit.agents import llm
    from livekit.agents.voice.run_result import RunEvent

    from app.config import Settings

_console = Console(highlight=False)


def print_banner(
    *,
    doc_id: str | None,
    user_id: str | None,
    doc_filename: str | None = None,
    user_email: str | None = None,
    settings: Settings | None = None,
) -> None:
    lines = ["[bold]mathbird tutor[/bold]", _format_setup_line("Document", doc_id, doc_filename)]
    lines.append(_format_setup_line("User", user_id, user_email))
    if settings is not None:
        lines.append(f"Grader    [yellow]{settings.grader}[/yellow]")
        lines.append(f"RAG       [yellow]{settings.rag_provider}[/yellow]")
    lines.append("[dim]Type a message · Ctrl+C to exit[/dim]")
    _console.print()
    _console.print(
        Panel(
            "\n".join(lines),
            border_style="bright_blue",
            padding=(0, 1),
        )
    )
    _console.print()


def _format_setup_line(label: str, value_id: str | None, detail: str | None) -> str:
    if not value_id:
        return f"{label:<9} [dim]none[/dim]"
    text = f"[cyan]{_short_id(value_id)}[/cyan]"
    if detail:
        text = f"{text}  {detail}"
    return f"{label:<9} {text}"


def print_user_message(text: str) -> None:
    _console.print()
    _console.print(Text("You", style="bold bright_cyan"))
    body = textwrap.fill(text.strip(), width=_console.width - 4, subsequent_indent="  ")
    for line in body.splitlines():
        _console.print(f"  {line}")


def print_tutor_message(text: str) -> None:
    _console.print()
    _console.print(Text("Tutor", style="bold bright_green"))
    content = text.strip()
    if not content:
        _console.print("  [dim](empty)[/dim]")
        return
    if len(content) <= 120 and "\n" not in content:
        _console.print(f"  {content}")
    else:
        wrapped = textwrap.fill(content, width=_console.width - 4, subsequent_indent="  ")
        for line in wrapped.splitlines():
            _console.print(f"  {line}")


def print_tool_call(name: str, arguments: str) -> None:
    summary = _summarize_tool_args(name, arguments)
    _console.print(f"  [dim]⎿[/dim] [bold magenta]{name}[/bold magenta][dim]({summary})[/dim]")


def print_tool_output(name: str, output: str, *, is_error: bool = False) -> None:
    style = "red" if is_error else "dim"
    preview = _truncate(output.replace("\n", " "), 100)
    _console.print(f"  [dim]↳[/dim] [{style}]{name}: {preview}[/{style}]")


def print_turn_divider() -> None:
    _console.print(Rule(style="dim"))


def print_dim(text: str) -> None:
    _console.print(text)


def format_run_event(event: RunEvent) -> dict[str, object]:
    """JSON-serializable view of a ``RunResult`` event (for ``simulate_conversation -v``)."""
    if event.type == "message":
        return {
            "type": "message",
            "role": event.item.role,
            "text": event.item.text_content,
        }
    if event.type == "function_call":
        return {
            "type": "function_call",
            "name": event.item.name,
            "arguments": event.item.arguments,
        }
    if event.type == "function_call_output":
        return {
            "type": "function_call_output",
            "name": event.item.name,
            "output": event.item.output,
            "is_error": event.item.is_error,
        }
    return {"type": event.type}


def render_run_events(events: list[RunEvent], *, skip_user: bool = False) -> None:
    """Pretty-print a turn's ``RunResult`` events (user, tools, tutor)."""
    for event in events:
        if event.type == "message":
            role = event.item.role
            text = event.item.text_content
            if not text:
                continue
            if role == "user":
                if skip_user:
                    continue
                print_user_message(text)
            elif role == "assistant":
                print_tutor_message(text)
        elif event.type == "function_call":
            print_tool_call(event.item.name, event.item.arguments or "")
        elif event.type == "function_call_output":
            print_tool_output(
                event.item.name,
                event.item.output or "",
                is_error=bool(event.item.is_error),
            )


def print_latest_assistant_from_history(history: llm.ChatContext) -> None:
    for item in reversed(history.items):
        if item.type == "message" and item.role == "assistant":
            text = item.text_content
            if text:
                print_tutor_message(text)
            return


def _summarize_tool_args(name: str, arguments: str) -> str:
    if not arguments:
        return ""
    try:
        payload = json.loads(arguments)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _truncate(arguments, 60)
    if name == "search_documents" and isinstance(payload, dict):
        query = payload.get("query")
        if isinstance(query, str):
            return _truncate(query, 60)
    if isinstance(payload, dict) and len(payload) == 1:
        return _truncate(str(next(iter(payload.values()))), 60)
    return _truncate(json.dumps(payload, ensure_ascii=False), 60)


def _short_id(value: str) -> str:
    return value if len(value) <= 16 else f"{value[:16]}…"


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"
