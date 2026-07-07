"""PDF upload, ingest, listing, and stream endpoints.

Upload is two-phase: ``POST /api/documents`` stores bytes and returns
``status="uploaded"``. ``POST /api/documents/{doc_id}/ingest`` schedules
background parse + index and returns ``status="ingesting"`` immediately.
Listing reads the sidecar to surface ingest progress. ``GET /api/documents/{doc_id}/file``
streams the PDF for the in-session iframe viewer.
"""

from __future__ import annotations

import io
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlparse
from urllib.request import url2pathname

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import User, get_current_user, get_optional_user
from app.config import get_settings
from app.documents.access import (
    assert_doc_access,
    assert_doc_access_optional,
    filter_summaries_for_guest,
    filter_summaries_for_user,
)
from app.documents.catalog import (
    SIDECAR_NAME,
    SYLLABUS_NAME,
    filename_from_storage_key,
    list_document_summaries,
)
from app.documents.ingest_jobs import (
    ingest_status_from_meta,
    is_ingest_running,
    mark_ingesting,
    schedule_ingest,
)
from app.documents.ingest_work import read_document_meta, write_document_meta
from app.storage import StoredObject, get_storage
from app.storage.utils import open_storage_stream
from app.syllabus import Syllabus, load_syllabus

router = APIRouter()
logger = logging.getLogger("mathbird.api.documents")

DocStatus = Literal["uploaded", "ingesting", "indexed", "failed"]


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


def _document_response(
    doc_id: str,
    stored: StoredObject,
    meta: dict[str, Any],
) -> DocumentResponse:
    status = ingest_status_from_meta(meta)
    return DocumentResponse.from_stored(
        doc_id,
        stored,
        status=status,  # type: ignore[arg-type]
        syllabus_ready=bool(meta.get("syllabus_ready")),
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


async def _read_bounded_pdf(file: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"PDF exceeds maximum upload size of {max_bytes} bytes.",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only valid PDF files are accepted.")
    return data


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF document to ingest")],
    user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    if (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="Only application/pdf is accepted.")

    settings = get_settings()
    pdf_bytes = await _read_bounded_pdf(file, max_bytes=settings.max_upload_bytes)

    doc_id = uuid.uuid4().hex
    safe_name = (file.filename or "document.pdf").replace("/", "_")
    key = f"{doc_id}/{safe_name}"

    storage = get_storage()
    stored = await storage.put(key, io.BytesIO(pdf_bytes), content_type="application/pdf")
    await write_document_meta(
        storage,
        doc_id,
        {
            "uploaded_by_user_id": user.id,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "ingest_status": "uploaded",
        },
    )
    return DocumentResponse.from_stored(doc_id, stored, status="uploaded")


@router.post("/documents/{doc_id}/ingest", response_model=DocumentResponse)
async def ingest_document(
    doc_id: str,
    user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
) -> DocumentResponse | JSONResponse:
    storage = get_storage()
    objects = await storage.list()
    stored = _find_stored_pdf(objects, doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    await assert_doc_access(storage, doc_id, user)

    meta = await read_document_meta(storage, doc_id)
    status = ingest_status_from_meta(meta)

    if status == "indexed":
        return _document_response(doc_id, stored, meta)

    if status == "ingesting" and is_ingest_running(doc_id):
        body = _document_response(doc_id, stored, meta)
        return JSONResponse(status_code=202, content=body.model_dump())

    await mark_ingesting(storage, doc_id)
    if not schedule_ingest(doc_id, background_tasks=background_tasks):
        meta = await read_document_meta(storage, doc_id)
        body = _document_response(doc_id, stored, meta)
        return JSONResponse(status_code=202, content=body.model_dump())

    meta = await read_document_meta(storage, doc_id)
    body = _document_response(doc_id, stored, meta)
    return JSONResponse(status_code=202, content=body.model_dump())


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> DocumentListResponse:
    settings = get_settings()
    summaries = await list_document_summaries()
    if user is not None:
        visible = filter_summaries_for_user(summaries, user, settings=settings)
    elif settings.guest_sample_doc_id:
        visible = filter_summaries_for_guest(summaries, settings=settings)
    else:
        raise HTTPException(status_code=401, detail="Authentication required.")

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
            for summary in visible
        ]
    )


@router.get("/documents/{doc_id}/syllabus", response_model=Syllabus)
async def get_document_syllabus(
    doc_id: str,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> Syllabus:
    storage = get_storage()
    await assert_doc_access_optional(storage, doc_id, user)
    syllabus = await load_syllabus(storage, doc_id)
    if syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found.")
    return syllabus


@router.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    user: Annotated[User | None, Depends(get_optional_user)],
):
    storage = get_storage()
    await assert_doc_access_optional(storage, doc_id, user)
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
        async with open_storage_stream(storage, stored.key) as stream:
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
