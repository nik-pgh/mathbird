"""Storage backend interface + factory."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import BinaryIO, Protocol, runtime_checkable

from app.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    """Result of a successful upload."""

    key: str         # storage-internal identifier (filename, S3 key, ...)
    uri: str         # canonical URI for retrieval (file:// or s3://)
    size: int        # bytes
    content_type: str


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal interface every storage backend implements."""

    async def put(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str,
    ) -> StoredObject: ...

    async def open(self, key: str) -> BinaryIO: ...

    async def list(self, prefix: str = "") -> list[StoredObject]: ...

    async def delete(self, key: str) -> None: ...


@lru_cache
def get_storage() -> StorageBackend:
    """Return the configured storage backend.

    Reads ``STORAGE_BACKEND`` once and caches the instance.
    """
    settings = get_settings()
    backend = settings.storage_backend

    if backend == "local":
        from .local import LocalStorage

        return LocalStorage(root=settings.storage_local_dir)

    if backend == "s3":
        from .s3 import S3Storage

        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key=settings.aws_access_key_id or None,
            secret_key=settings.aws_secret_access_key or None,
        )

    raise ValueError(f"Unknown storage backend: {backend}")
