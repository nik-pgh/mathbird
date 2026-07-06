"""Tests for tutor board injection formatting."""

from __future__ import annotations

from app.agent.turn_context.tutor_board import format_tutor_board_injection
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.messages import AiBoardDiagram, AiBoardPlot, AiBoardText


def test_format_tutor_board_empty() -> None:
    text = format_tutor_board_injection(BoardCache())

    assert text.startswith("[tutor board]")
    assert "automatically" in text
    assert "Do not say you cannot draw" in text
    assert "(currently empty)" in text


def test_format_tutor_board_lists_items() -> None:
    cache = BoardCache()
    cache.apply(
        [
            AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$"),
            AiBoardPlot(kind="plot", id="p1", expression="x**2", label="Parabola"),
            AiBoardDiagram(
                kind="diagram",
                id="d1",
                syntax="mermaid",
                source="flowchart TD\n  A --> B",
                label="Steps",
            ),
        ]
    )

    text = format_tutor_board_injection(cache)

    assert "eq1 (text): $2x + 5 = 10$" in text
    assert "p1 (plot): y = x**2" in text
    assert 'd1 (diagram "Steps")' in text
