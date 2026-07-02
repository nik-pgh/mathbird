"""Persist student progress JSON in storage."""

from __future__ import annotations

import io
import json
from typing import Any, Protocol, runtime_checkable

from app.progress.models import ProgressState
from app.storage.utils import open_storage_stream

PROGRESS_FILENAME = "progress.json"


def progress_key(user_id: str, doc_id: str) -> str:
    return f"{user_id}/{doc_id}/{PROGRESS_FILENAME}"


@runtime_checkable
class ProgressStore(Protocol):
    async def load(self, user_id: str, doc_id: str) -> ProgressState | None: ...

    async def save(self, state: ProgressState) -> None: ...


class StorageProgressStore:
    def __init__(self, storage: Any) -> None:
        self._storage = storage

    async def load(self, user_id: str, doc_id: str) -> ProgressState | None:
        try:
            async with open_storage_stream(self._storage, progress_key(user_id, doc_id)) as stream:
                payload = json.loads(stream.read().decode("utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
            return None
        return ProgressState.model_validate(payload)

    async def save(self, state: ProgressState) -> None:
        body = json.dumps(state.model_dump(mode="json")).encode("utf-8")
        await self._storage.put(
            progress_key(state.user_id, state.doc_id),
            io.BytesIO(body),
            content_type="application/json",
        )


def get_progress_store(storage: Any) -> ProgressStore:
    return StorageProgressStore(storage)
