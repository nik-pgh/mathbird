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
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlparse
from urllib.request import url2pathname

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import User, get_current_user
from app.config import get_settings
from app.documents.access import (
    assert_doc_access,
    filter_summaries_for_user,
    read_document_meta,
)
from app.documents.catalog import (
    SIDECAR_NAME,
    SYLLABUS_NAME,
    filename_from_storage_key,
    list_document_summaries,
    sidecar_key,
)
from app.rag import get_retriever
from app.storage import StoredObject, get_storage
from app.syllabus import Syllabus, build_heuristic_syllabus, load_syllabus, save_syllabus
from app.syllabus.parse import parse_pdf_to_document

router = APIRouter()
logger = logging.getLogger("mathbird.api.documents")

DocStatus = Literal["uploaded", "indexed", "failed"]


class DocumentResponse(BaseModel):
    doc_id: str
    key: str
    uri: str
    size: int
    content_type: str
    status: DocStatus = "uploaded"
    syllabus_ready: bool = False

    @classmethod
    def from_stored(
        cls,
        doc_id: str,
        obj: StoredObject,
        *,
        status: DocStatus = "uploaded",
        syllabus_ready: bool = False,
    ) -> DocumentResponse:
        return cls(
            doc_id=doc_id,
            key=obj.key,
            uri=obj.uri,
            size=obj.size,
            content_type=obj.content_type,
            status=status,
            syllabus_ready=syllabus_ready,
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


async def _read_sidecar(storage: Any, doc_id: str) -> dict[str, Any]:
    try:
        async with _open_storage_stream(storage, sidecar_key(doc_id)) as stream:
            payload = json.loads(stream.read().decode("utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


@asynccontextmanager
async def _local_pdf_path(storage: Any, stored: StoredObject) -> AsyncIterator[str]:
    if stored.uri.startswith("file://"):
        yield _path_from_file_uri(stored.uri)
        return

    temp_dir = tempfile.mkdtemp()
    try:
        temp_path = Path(temp_dir) / filename_from_storage_key(stored.key)
        with temp_path.open("wb") as temp_file:
            async with _open_storage_stream(storage, stored.key) as source:
                shutil.copyfileobj(source, temp_file)
        yield str(temp_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _maybe_build_syllabus(
    storage: Any,
    *,
    doc_id: str,
    pdf_path: str,
) -> tuple[bool, str | None]:
    settings = get_settings()
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


def _path_from_file_uri(uri: str) -> str:
    parsed = urlparse(uri)
    return url2pathname(parsed.path)


def _content_disposition(filename: str) -> str:
    fallback = "".join(
        ch if 0x20 <= ord(ch) < 0x7F and ch not in {'"', "\\", ";"} else "_"
        for ch in filename
    ).strip()
    fallback = fallback or "document.pdf"
    encoded = quote(filename, safe="")
    return f'inline; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


async def _write_sidecar(storage: Any, doc_id: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await storage.put(
        sidecar_key(doc_id),
        io.BytesIO(body),
        content_type="application/json",
    )


def _find_stored_pdf(objects: list[StoredObject], doc_id: str) -> StoredObject | None:
    prefix = f"{doc_id}/"
    for obj in objects:
        if not obj.key.startswith(prefix):
            continue
        if obj.key.endswith(f"/{SIDECAR_NAME}") or obj.key.endswith(f"/{SYLLABUS_NAME}"):
            continue
        return obj
    return None


# ── routes ──────────────────────────────────────────────────────────────────


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF document to ingest")],
    user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    if (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="Only application/pdf is accepted.")

    doc_id = uuid.uuid4().hex
    safe_name = (file.filename or "document.pdf").replace("/", "_")
    key = f"{doc_id}/{safe_name}"

    storage = get_storage()
    stored = await storage.put(key, file.file, content_type="application/pdf")
    await _write_sidecar(
        storage,
        doc_id,
        {
            "uploaded_by_user_id": user.id,
            "uploaded_at": datetime.now(UTC).isoformat(),
        },
    )
    return DocumentResponse.from_stored(doc_id, stored, status="uploaded")


@router.post("/documents/{doc_id}/ingest", response_model=DocumentResponse)
async def ingest_document(
    doc_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    storage = get_storage()
    objects = await storage.list()
    stored = _find_stored_pdf(objects, doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    await assert_doc_access(storage, doc_id, user)

    try:
        async with _local_pdf_path(storage, stored) as pdf_path:
            await get_retriever().ingest_pdf(pdf_path, doc_id=doc_id)
            syllabus_ready, syllabus_error = await _maybe_build_syllabus(
                storage,
                doc_id=doc_id,
                pdf_path=pdf_path,
            )
    except Exception as exc:
        logger.exception("Document ingestion failed for doc_id=%s key=%s", doc_id, stored.key)
        raise HTTPException(status_code=502, detail="Document ingestion failed.") from exc
    existing = await read_document_meta(storage, doc_id)
    sidecar_payload: dict[str, Any] = {
        **existing,
        "indexed": True,
        "indexed_at": datetime.now(UTC).isoformat(),
        "syllabus_ready": syllabus_ready,
    }
    if syllabus_error:
        sidecar_payload["syllabus_error"] = syllabus_error
    await _write_sidecar(storage, doc_id, sidecar_payload)
    return DocumentResponse.from_stored(
        doc_id,
        stored,
        status="indexed",
        syllabus_ready=syllabus_ready,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    user: Annotated[User, Depends(get_current_user)],
) -> DocumentListResponse:
    summaries = filter_summaries_for_user(await list_document_summaries(), user)
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                doc_id=summary.doc_id,
                key=summary.key,
                uri=summary.uri,
                size=summary.size,
                content_type=summary.content_type,
                status=summary.status,
                syllabus_ready=summary.syllabus_ready,
            )
            for summary in summaries
        ]
    )


@router.get("/documents/{doc_id}/syllabus", response_model=Syllabus)
async def get_document_syllabus(
    doc_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> Syllabus:
    storage = get_storage()
    await assert_doc_access(storage, doc_id, user)
    syllabus = await load_syllabus(storage, doc_id)
    if syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found.")
    return syllabus


@router.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    user: Annotated[User, Depends(get_current_user)],
):
    storage = get_storage()
    await assert_doc_access(storage, doc_id, user)
    objects = await storage.list()
    stored = _find_stored_pdf(objects, doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    filename = filename_from_storage_key(stored.key)
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
