"""Tests for TurnContextBuilder board and progress injections."""

from __future__ import annotations

from app.agent.turn_context.builder import TurnContextBuilder
from app.agent.whiteboard.state import BoardState
from tests.progress.test_engine import _engine


def test_board_injection_none_when_no_refresh() -> None:
    builder = TurnContextBuilder(board_state=BoardState(), progress_engine=None)

    assert builder.board_injection() is None


def test_board_injection_with_text() -> None:
    state = BoardState()
    state.record_reading("x = 2 + 3")
    builder = TurnContextBuilder(board_state=state, progress_engine=None)

    block = builder.board_injection()

    assert block is not None
    assert block.kind == "board"
    assert "x = 2 + 3" in block.content


def test_progress_injection_matches_format_injection() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    builder = TurnContextBuilder(board_state=BoardState(), progress_engine=engine)

    block = builder.progress_injection()

    assert block is not None
    assert block.kind == "progress"
    assert block.content == engine.format_injection()


def test_progress_injection_none_without_engine() -> None:
    builder = TurnContextBuilder(board_state=BoardState(), progress_engine=None)

    assert builder.progress_injection() is None


def test_base_injections_order_board_before_progress() -> None:
    state = BoardState()
    state.record_reading("y = 5")
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    builder = TurnContextBuilder(board_state=state, progress_engine=engine)

    blocks = builder.base_injections()

    assert len(blocks) == 2
    assert blocks[0].kind == "board"
    assert blocks[1].kind == "progress"


def test_base_injections_skips_none() -> None:
    builder = TurnContextBuilder(board_state=BoardState(), progress_engine=None)

    assert builder.base_injections() == ()
