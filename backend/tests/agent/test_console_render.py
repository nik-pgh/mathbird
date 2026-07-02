"""Tests for Rich turn panel rendering."""

from __future__ import annotations

import io

import pytest
from livekit.agents.llm import ChatMessage, FunctionCall, FunctionCallOutput
from livekit.agents.voice.run_result import RunResult
from rich.console import Console

from app.agent.console import render as render_module
from app.agent.console.render import assistant_reply, render_turn_panel
from app.agent.turn_context import InjectionBlock, TurnContextSnapshot, classify_injection_kind


def _run_with_events(items) -> RunResult:
    run = RunResult(user_input="test", output_type=None)
    for item in items:
        run._item_added(item)
    run._mark_done_if_needed(None)
    return run


def test_classify_injection_kind_empty_content() -> None:
    assert classify_injection_kind("") == "other"


def test_render_turn_panel_empty_snapshot(capsys: pytest.CaptureFixture[str]) -> None:
    run = _run_with_events([])
    snapshot = TurnContextSnapshot(injections=())

    render_turn_panel(
        turn_number=1,
        user_text="",
        context=snapshot,
        run=run,
        engine=None,
    )

    captured = capsys.readouterr()
    assert "Turn 1" in captured.out
    assert "👤 You" in captured.out
    assert "📥 Injected context" in captured.out
    assert "(none)" in captured.out
    assert "🔧 Tools" in captured.out
    assert "(none this turn)" in captured.out
    assert "🎓 Tutor" in captured.out
    assert "(empty)" in captured.out
    assert "📈 Progress after grader" in captured.out
    assert "progression tracking off" in captured.out


def test_render_turn_panel_with_injections_and_tools(capsys: pytest.CaptureFixture[str]) -> None:
    snapshot = TurnContextSnapshot(
        injections=(
            InjectionBlock(kind="board", content="[user whiteboard]\nno reading yet"),
            InjectionBlock(kind="progress", content="[session progress]\nfocus: ch-1-p-1"),
        )
    )
    run = _run_with_events(
        [
            FunctionCall(
                call_id="1",
                name="search_documents",
                arguments='{"query": "derivatives"}',
            ),
            FunctionCallOutput(
                call_id="1",
                name="search_documents",
                output="excerpt from textbook",
                is_error=False,
            ),
            ChatMessage(role="assistant", content=["Let's look at problem 1."]),
        ]
    )

    render_turn_panel(
        turn_number=2,
        user_text="help me with derivatives",
        context=snapshot,
        run=run,
        engine=None,
    )

    captured = capsys.readouterr()
    assert "Turn 2" in captured.out
    assert "help me with derivatives" in captured.out
    assert "🖊" in captured.out
    assert "📊" in captured.out
    assert "search_documents" in captured.out
    assert "Let's look at problem 1." in captured.out


def test_assistant_reply_concatenates_messages() -> None:
    run = _run_with_events(
        [
            ChatMessage(role="assistant", content=["First part."]),
            ChatMessage(role="user", content=["ignored"]),
            ChatMessage(role="assistant", content=["Second part."]),
        ]
    )

    assert assistant_reply(run.events) == "First part.\nSecond part."


def test_assistant_reply_skips_empty_assistant_messages() -> None:
    run = _run_with_events(
        [
            ChatMessage(role="assistant", content=[""]),
            ChatMessage(role="assistant", content=["Only this."]),
        ]
    )

    assert assistant_reply(run.events) == "Only this."


def test_render_turn_panel_captures_to_console_buffer() -> None:
    """Smoke test that render works when console output is redirected."""
    buffer = io.StringIO()
    original = render_module._console
    render_module._console = Console(file=buffer, highlight=False, width=120)
    try:
        render_turn_panel(
            turn_number=1,
            user_text="hi",
            context=TurnContextSnapshot(injections=()),
            run=_run_with_events([]),
            engine=None,
        )
    finally:
        render_module._console = original

    output = buffer.getvalue()
    assert "Turn 1" in output
    assert "hi" in output
