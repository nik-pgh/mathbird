"""Shared helpers for storage backend duck-typing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


@asynccontextmanager
async def open_storage_stream(storage: Any, key: str) -> AsyncIterator[Any]:
    opened = storage.open(key)
    if hasattr(opened, "__await__"):
        opened = await opened

    if hasattr(opened, "__aenter__"):
        async with opened as stream:
            yield stream
        return

    try:
        yield opened
    finally:
        close = getattr(opened, "close", None)
        if close is not None:
            close()
