"""PDF upload + listing endpoints.

Uploaded PDFs are persisted via the active :class:`StorageBackend` and
forwarded to the active :class:`Retriever` for ingestion. Today the retriever
is a no-op, so this route just stores the file; once a real RAG framework is
wired up, the same code path will index the document.
"""

from __future__ import annotations

import uuid
from typing import Annotated

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

    # Hand off to the retriever for indexing. NullRetriever is a no-op today;
    # a real implementation will chunk + embed + store vectors here.
    retriever = get_retriever()
    # Resolve a filesystem path the retriever can read. For local storage the
    # URI is file://, for S3 the retriever will need to download. Keeping this
    # simple for now — production RAG backends will likely want the raw stream.
    path = stored.uri.removeprefix("file://") if stored.uri.startswith("file://") else stored.uri
    await retriever.ingest_pdf(path, doc_id=doc_id)

    return DocumentResponse.from_stored(doc_id, stored)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents() -> DocumentListResponse:
    storage = get_storage()
    objects = await storage.list()
    docs = [
        DocumentResponse.from_stored(obj.key.split("/", 1)[0], obj)
        for obj in objects
    ]
    return DocumentListResponse(documents=docs)
