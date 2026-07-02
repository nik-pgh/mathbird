"""Local filesystem storage backend."""

from __future__ import annotations

import asyncio
import mimetypes
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import BinaryIO

from .base import StoredObject


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Defend against path traversal — strip any leading separator and
        # resolve relative to root, then verify the result is still inside root.
        candidate = (self.root / key.lstrip("/\\")).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Invalid storage key: {key}")
        return candidate

    def _put_sync(self, key: str, data: BinaryIO, *, content_type: str) -> StoredObject:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            shutil.copyfileobj(data, f)
        size = dest.stat().st_size
        return StoredObject(
            key=key,
            uri=dest.as_uri(),
            size=size,
            content_type=content_type,
        )

    async def put(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str,
    ) -> StoredObject:
        return await asyncio.to_thread(self._put_sync, key, data, content_type=content_type)

    @asynccontextmanager
    async def open(self, key: str) -> AsyncIterator[BinaryIO]:
        path = self._path(key)

        def _open() -> BinaryIO:
            return path.open("rb")

        stream = await asyncio.to_thread(_open)
        try:
            yield stream
        finally:
            await asyncio.to_thread(stream.close)

    def _list_sync(self, prefix: str) -> list[StoredObject]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return []
        results: list[StoredObject] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel_key = str(path.relative_to(self.root))
            content_type, _ = mimetypes.guess_type(path.name)
            results.append(
                StoredObject(
                    key=rel_key,
                    uri=path.as_uri(),
                    size=path.stat().st_size,
                    content_type=content_type or "application/octet-stream",
                )
            )
        return results

    async def list(self, prefix: str = "") -> list[StoredObject]:
        return await asyncio.to_thread(self._list_sync, prefix)

    async def delete(self, key: str) -> None:
        path = self._path(key)

        def _delete() -> None:
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_delete)
