"""Persist syllabi alongside uploaded PDFs."""

from __future__ import annotations

import io
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.syllabus.models import Syllabus

SYLLABUS_FILENAME = "syllabus.json"


def syllabus_key(doc_id: str) -> str:
    return f"{doc_id}/{SYLLABUS_FILENAME}"


async def save_syllabus(storage: Any, doc_id: str, syllabus: Syllabus) -> None:
    body = json.dumps(syllabus.model_dump(mode="json")).encode("utf-8")
    await storage.put(
        syllabus_key(doc_id),
        io.BytesIO(body),
        content_type="application/json",
    )


@asynccontextmanager
async def _open_storage_stream(storage: Any, key: str) -> AsyncIterator[Any]:
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


async def load_syllabus(storage: Any, doc_id: str) -> Syllabus | None:
    try:
        async with _open_storage_stream(storage, syllabus_key(doc_id)) as stream:
            payload = json.loads(stream.read().decode("utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    return Syllabus.model_validate(payload)
