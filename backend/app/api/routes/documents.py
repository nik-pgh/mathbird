"""PDF upload, ingest, listing, and stream endpoints.

Upload is two-phase: ``POST /api/documents`` stores bytes and returns
``status="uploaded"``. ``POST /api/documents/{doc_id}/ingest`` runs the
synchronous parse + index step and writes a ``{doc_id}/meta.json`` sidecar
marking the document indexed. Listing reads the sidecar to surface the
current state. ``GET /api/documents/{doc_id}/file`` streams the PDF for
the in-session iframe viewer.
"""

from __future__ import annotations

import io
import json
import logging
import posixpath
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote, unquote, urlparse
from urllib.request import url2pathname

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import User, get_current_user
from app.rag import get_retriever
from app.storage import StoredObject, get_storage

router = APIRouter()
logger = logging.getLogger("mathbird.api.documents")

DocStatus = Literal["uploaded", "indexed", "failed"]

_SIDECAR_NAME = "meta.json"


class DocumentResponse(BaseModel):
    doc_id: str
    key: str
    uri: str
    size: int
    content_type: str
    status: DocStatus = "uploaded"

    @classmethod
    def from_stored(
        cls,
        doc_id: str,
        obj: StoredObject,
        *,
        status: DocStatus = "uploaded",
    ) -> DocumentResponse:
        return cls(
            doc_id=doc_id,
            key=obj.key,
            uri=obj.uri,
            size=obj.size,
            content_type=obj.content_type,
            status=status,
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


# ── helpers ─────────────────────────────────────────────────────────────────


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


async def _ingest_stored_pdf(storage: Any, stored: StoredObject, *, doc_id: str) -> None:
    retriever = get_retriever()
    if stored.uri.startswith("file://"):
        await retriever.ingest_pdf(_path_from_file_uri(stored.uri), doc_id=doc_id)
        return

    temp_dir = ""
    try:
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / _filename_from_storage_key(stored.key)
        with temp_path.open("wb") as temp_file:
            async with _open_storage_stream(storage, stored.key) as source:
                shutil.copyfileobj(source, temp_file)
        await retriever.ingest_pdf(str(temp_path), doc_id=doc_id)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _path_from_file_uri(uri: str) -> str:
    parsed = urlparse(uri)
    return url2pathname(parsed.path)


def _filename_from_storage_key(key: str) -> str:
    filename = posixpath.basename(unquote(key.strip("/")).replace("\\", "/"))
    return filename or "document.pdf"


def _content_disposition(filename: str) -> str:
    fallback = "".join(
        ch if 0x20 <= ord(ch) < 0x7F and ch not in {'"', "\\", ";"} else "_"
        for ch in filename
    ).strip()
    fallback = fallback or "document.pdf"
    encoded = quote(filename, safe="")
    return f'inline; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def _sidecar_key(doc_id: str) -> str:
    return f"{doc_id}/{_SIDECAR_NAME}"


async def _write_sidecar(storage: Any, doc_id: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await storage.put(
        _sidecar_key(doc_id),
        io.BytesIO(body),
        content_type="application/json",
    )


def _find_stored_pdf(objects: list[StoredObject], doc_id: str) -> StoredObject | None:
    prefix = f"{doc_id}/"
    for obj in objects:
        if obj.key.startswith(prefix) and not obj.key.endswith(f"/{_SIDECAR_NAME}"):
            return obj
    return None


# ── routes ──────────────────────────────────────────────────────────────────


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF document to ingest")],
    _user: User = Depends(get_current_user),
) -> DocumentResponse:
    if (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="Only application/pdf is accepted.")

    doc_id = uuid.uuid4().hex
    safe_name = (file.filename or "document.pdf").replace("/", "_")
    key = f"{doc_id}/{safe_name}"

    storage = get_storage()
    stored = await storage.put(key, file.file, content_type="application/pdf")
    return DocumentResponse.from_stored(doc_id, stored, status="uploaded")


@router.post("/documents/{doc_id}/ingest", response_model=DocumentResponse)
async def ingest_document(
    doc_id: str,
    _user: User = Depends(get_current_user),
) -> DocumentResponse:
    storage = get_storage()
    objects = await storage.list()
    stored = _find_stored_pdf(objects, doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        await _ingest_stored_pdf(storage, stored, doc_id=doc_id)
    except Exception as exc:
        logger.exception("Document ingestion failed for doc_id=%s key=%s", doc_id, stored.key)
        raise HTTPException(status_code=502, detail="Document ingestion failed.") from exc

    await _write_sidecar(
        storage,
        doc_id,
        {"indexed": True, "indexed_at": datetime.now(UTC).isoformat()},
    )
    return DocumentResponse.from_stored(doc_id, stored, status="indexed")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(_user: User = Depends(get_current_user)) -> DocumentListResponse:
    storage = get_storage()
    objects = await storage.list()

    # Group by doc_id; ignore sidecars in the public listing.
    docs: dict[str, StoredObject] = {}
    sidecar_doc_ids: set[str] = set()
    for obj in objects:
        head, _, tail = obj.key.partition("/")
        if not tail:
            continue
        if tail == _SIDECAR_NAME:
            sidecar_doc_ids.add(head)
            continue
        # First non-sidecar entry per doc_id wins.
        docs.setdefault(head, obj)

    results: list[DocumentResponse] = []
    for doc_id, obj in docs.items():
        status: DocStatus = "indexed" if doc_id in sidecar_doc_ids else "uploaded"
        results.append(DocumentResponse.from_stored(doc_id, obj, status=status))
    return DocumentListResponse(documents=results)


@router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str, _user: User = Depends(get_current_user)):
    storage = get_storage()
    objects = await storage.list()
    stored = _find_stored_pdf(objects, doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    filename = _filename_from_storage_key(stored.key)
    content_disposition = _content_disposition(filename)

    if stored.uri.startswith("file://"):
        return FileResponse(
            _path_from_file_uri(stored.uri),
            media_type="application/pdf",
            headers={"Content-Disposition": content_disposition},
        )

    async def _iter() -> AsyncIterator[bytes]:
        async with _open_storage_stream(storage, stored.key) as stream:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )
