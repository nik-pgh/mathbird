"""Persist syllabi alongside uploaded PDFs."""

from __future__ import annotations

import io
import json
from typing import Any

from app.storage.utils import open_storage_stream
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


async def load_syllabus(storage: Any, doc_id: str) -> Syllabus | None:
    try:
        async with open_storage_stream(storage, syllabus_key(doc_id)) as stream:
            payload = json.loads(stream.read().decode("utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    return Syllabus.model_validate(payload)
