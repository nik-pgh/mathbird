"""PDF upload + listing endpoints.

Uploaded PDFs are persisted via the active :class:`StorageBackend` and
forwarded to the active :class:`Retriever` for ingestion. The default null
provider is a no-op, while ``RAG_PROVIDER=llamaindex_qdrant`` parses and indexes
the PDF through the built-in RAG pipeline.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.rag import get_retriever
from app.storage import StoredObject, get_storage

router = APIRouter()


class DocumentResponse(BaseModel):
    doc_id: str
    key: str
    uri: str
    size: int
    content_type: str

    @classmethod
    def from_stored(cls, doc_id: str, obj: StoredObject) -> DocumentResponse:
        return cls(
            doc_id=doc_id,
            key=obj.key,
            uri=obj.uri,
            size=obj.size,
            content_type=obj.content_type,
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


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
        await retriever.ingest_pdf(stored.uri.removeprefix("file://"), doc_id=doc_id)
        return

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = temp_file.name
            async with _open_storage_stream(storage, stored.key) as source:
                shutil.copyfileobj(source, temp_file)
        await retriever.ingest_pdf(temp_path, doc_id=doc_id)
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF document to ingest")],
) -> DocumentResponse:
    if (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="Only application/pdf is accepted.")

    doc_id = uuid.uuid4().hex
    # Keep the original filename for human readability but namespace by doc_id
    # so collisions are impossible.
    safe_name = (file.filename or "document.pdf").replace("/", "_")
    key = f"{doc_id}/{safe_name}"

    storage = get_storage()
    stored = await storage.put(key, file.file, content_type="application/pdf")

    # Hand off to the retriever for indexing. The default null provider is a
    # no-op; RAG_PROVIDER=llamaindex_qdrant parses and indexes the PDF.
    await _ingest_stored_pdf(storage, stored, doc_id=doc_id)

    return DocumentResponse.from_stored(doc_id, stored)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents() -> DocumentListResponse:
    storage = get_storage()
    objects = await storage.list()
    docs = [DocumentResponse.from_stored(obj.key.split("/", 1)[0], obj) for obj in objects]
    return DocumentListResponse(documents=docs)
