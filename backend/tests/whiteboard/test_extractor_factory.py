"""``get_board_extractor`` selects the implementation by env."""

from __future__ import annotations

import pytest

from app.agent.whiteboard.extractor.factory import get_board_extractor
from app.agent.whiteboard.extractor.null import NullExtractor
from app.config import get_settings


def _clear_caches() -> None:
    get_board_extractor.cache_clear()
    get_settings.cache_clear()


def test_factory_defaults_to_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOARD_EXTRACTOR", raising=False)
    _clear_caches()
    ex = get_board_extractor()
    assert isinstance(ex, NullExtractor)


def test_factory_returns_openai_when_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_EXTRACTOR", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _clear_caches()

    from app.agent.whiteboard.extractor.openai import OpenAIBoardExtractor

    ex = get_board_extractor()
    assert isinstance(ex, OpenAIBoardExtractor)


def test_factory_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_EXTRACTOR", "bogus")
    _clear_caches()
    with pytest.raises(ValueError, match="bogus"):
        get_board_extractor()
