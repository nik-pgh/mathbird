"""``get_board_extractor`` — env-driven factory for board extractors."""

from __future__ import annotations

from functools import lru_cache

from app.agent.whiteboard.extractor.base import BoardExtractor
from app.config import get_settings


@lru_cache
def get_board_extractor() -> BoardExtractor:
    """Return the configured board extractor.

    Reads ``BOARD_EXTRACTOR`` once and caches the instance. Restart the
    worker to pick up env changes; tests should call
    ``get_board_extractor.cache_clear()``.
    """
    settings = get_settings()
    name = settings.board_extractor

    if name == "null":
        from .null import NullExtractor

        return NullExtractor()

    if name == "openai":
        from .openai import OpenAIBoardExtractor

        return OpenAIBoardExtractor(
            model=settings.board_extractor_model,
            timeout=settings.board_extractor_timeout_seconds,
            api_key=settings.openai_api_key or None,
        )

    raise ValueError(f"Unknown board extractor: {name}")
