"""Shared ingest helpers used by HTTP routes and background jobs."""

from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from app.config import Settings, get_settings
from app.documents.catalog import filename_from_storage_key, sidecar_key
from app.rag.retriever import Retriever
from app.storage import StoredObject
from app.storage.utils import open_storage_stream
from app.syllabus import build_heuristic_syllabus, save_syllabus
from app.syllabus.parse import parse_pdf_to_document

logger = logging.getLogger("mathbird.documents.ingest")


async def read_document_meta(storage: Any, doc_id: str) -> dict[str, Any]:
    try:
        async with open_storage_stream(storage, sidecar_key(doc_id)) as stream:
            payload = json.loads(stream.read().decode("utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to read sidecar for doc_id=%s: %s", doc_id, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


async def write_document_meta(storage: Any, doc_id: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    await storage.put(
        sidecar_key(doc_id),
        io.BytesIO(body),
        content_type="application/json",
    )


def _path_from_file_uri(uri: str) -> str:
    parsed = urlparse(uri)
    return url2pathname(parsed.path)


@asynccontextmanager
async def local_pdf_path(storage: Any, stored: StoredObject) -> AsyncIterator[str]:
    if stored.uri.startswith("file://"):
        yield _path_from_file_uri(stored.uri)
        return

    temp_dir = tempfile.mkdtemp()
    try:
        temp_path = Path(temp_dir) / filename_from_storage_key(stored.key)
        with temp_path.open("wb") as temp_file:
            async with open_storage_stream(storage, stored.key) as source:
                shutil.copyfileobj(source, temp_file)
        yield str(temp_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def maybe_build_syllabus(
    storage: Any,
    *,
    doc_id: str,
    pdf_path: str,
    settings: Settings | None = None,
) -> tuple[bool, str | None]:
    settings = settings or get_settings()
    if not settings.llamaparse_api_key:
        return False, "LLAMAPARSE_API_KEY not configured"
    try:
        document = await parse_pdf_to_document(pdf_path, doc_id=doc_id, settings=settings)
        syllabus = build_heuristic_syllabus(document)
        await save_syllabus(storage, doc_id, syllabus)
        return True, None
    except Exception as exc:
        logger.exception("Syllabus build failed for doc_id=%s path=%s", doc_id, pdf_path)
        return False, str(exc)


async def ingest_stored_pdf(
    storage: Any,
    stored: StoredObject,
    *,
    doc_id: str,
    retriever: Retriever,
) -> tuple[bool, str | None]:
    async with local_pdf_path(storage, stored) as pdf_path:
        await retriever.ingest_pdf(pdf_path, doc_id=doc_id)
        return await maybe_build_syllabus(storage, doc_id=doc_id, pdf_path=pdf_path)
