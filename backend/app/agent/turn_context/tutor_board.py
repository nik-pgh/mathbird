"""Format the tutor's AiBoard state for per-turn LLM injection."""

from __future__ import annotations

from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.messages import (
    AiBoardDiagram,
    AiBoardItem,
    AiBoardPlot,
    AiBoardShape,
    AiBoardText,
)

_MAX_LINE = 120


def format_tutor_board_injection(board_cache: BoardCache) -> str:
    """Build the ``[tutor board]`` system block shown to the tutor each turn."""
    items = board_cache.current_items()
    header = (
        "[tutor board]\n"
        "Your visual tutor cards on the shared canvas. They update automatically "
        "from your spoken explanations — reference them and guide the student "
        "to look at them. Do not say you cannot draw.\n"
    )
    if not items:
        return header + "\n(currently empty)"
    lines = [header, "Current cards:"]
    for item in items:
        lines.append(f"- {_summarize_item(item)}")
    return "\n".join(lines)


def _summarize_item(item: AiBoardItem) -> str:
    if isinstance(item, AiBoardText):
        return f"{item.id} (text): {_truncate(item.markdown)}"
    if isinstance(item, AiBoardPlot):
        bounds = f"[{item.x_min:g}, {item.x_max:g}]"
        label = f' "{item.label}"' if item.label else ""
        return f"{item.id} (plot): y = {item.expression} {bounds}{label}"
    if isinstance(item, AiBoardDiagram):
        label = f' "{item.label}"' if item.label else ""
        preview = _truncate(item.source.replace("\\n", " "))
        return f"{item.id} (diagram{label}): {preview}"
    if isinstance(item, AiBoardShape):
        return f"{item.id} (sketch)"
    return f"{item.id} ({item.kind})"


def _truncate(text: str, limit: int = _MAX_LINE) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 1].rstrip() + "…"
