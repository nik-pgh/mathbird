"""Pluggable object storage for uploaded PDFs.

The HTTP API only depends on :class:`StorageBackend`. Concrete backends:

* :class:`LocalStorage` — writes files to a directory on disk (default).
* :class:`S3Storage`    — writes to an AWS S3 bucket (use in production).

Pick which one is active via ``STORAGE_BACKEND`` in the environment.
"""

from .base import StorageBackend, StoredObject, get_storage
from .local import LocalStorage

__all__ = ["LocalStorage", "StorageBackend", "StoredObject", "get_storage"]
