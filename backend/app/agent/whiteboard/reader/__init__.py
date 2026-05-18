"""``BoardReader`` Protocol and factory.

A board reader turns a PNG snapshot of the student's canvas into a text /
LaTeX string the LLM can reason about. Implementations are duck-typed.

Add a new reader by:

1. Adding a module under ``app/agent/whiteboard/reader/`` that exposes a class
   implementing :class:`BoardReader`.
2. Adding the name to ``BoardReaderName`` in ``app/config.py``.
3. Adding the corresponding branch in :func:`get_board_reader` below.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.config import get_settings


@runtime_checkable
class BoardReader(Protocol):
    async def interpret(self, png_bytes: bytes) -> str: ...


@lru_cache
def get_board_reader() -> BoardReader:
    """Return the configured board reader.

    Reads ``BOARD_READER`` once and caches the instance. Restart the worker
    to pick up env changes; tests should ``get_board_reader.cache_clear()``.
    """
    settings = get_settings()
    name = settings.board_reader

    if name == "null":
        from .null import NullBoardReader

        return NullBoardReader()

    if name == "openai_vision":
        from .openai_vision import OpenAIVisionBoardReader

        return OpenAIVisionBoardReader(
            model=settings.board_reader_model,
            api_key=settings.openai_api_key or None,
        )

    raise ValueError(f"Unknown board reader: {name}")
