"""Tests for turn context snapshot types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.agent.turn_context import (
    InjectionBlock,
    TurnContextSnapshot,
    classify_injection_kind,
)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("[user whiteboard]\nno reading yet", "board"),
        ("[tutor board]\n(currently empty)", "board"),
        ("[session progress]\nfocus: ch-1-p-1", "progress"),
        ("[textbook excerpt]\nSome math text", "textbook"),
        ("[next action]\nAsk a question", "other"),
        ("", "other"),
    ],
)
def test_classify_injection_kind(content: str, expected: str) -> None:
    assert classify_injection_kind(content) == expected


def test_turn_context_snapshot_is_frozen() -> None:
    block = InjectionBlock(kind="board", content="[user whiteboard]\nempty")
    snapshot = TurnContextSnapshot(injections=(block,))

    with pytest.raises(FrozenInstanceError):
        snapshot.injections = ()  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        block.kind = "other"  # type: ignore[misc]
