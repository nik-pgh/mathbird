"""List uploaded PDFs from storage (shared by HTTP API and console prompts)."""

import posixpath
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import unquote

from app.storage import StoredObject, get_storage

DocStatus = Literal["uploaded", "ingesting", "indexed", "failed"]
SIDECAR_NAME = "meta.json"
SYLLABUS_NAME = "syllabus.json"


def ingest_status_from_meta(meta: dict[str, Any]) -> DocStatus:
    explicit = meta.get("ingest_status")
    if explicit in ("uploaded", "ingesting", "indexed", "failed"):
        return explicit  # type: ignore[return-value]
    if meta.get("indexed"):
        return "indexed"
    return "uploaded"


@dataclass(frozen=True)
class DocumentSummary:
    doc_id: str
    key: str
    uri: str
    filename: str
    status: DocStatus
    syllabus_ready: bool
    size: int
    content_type: str
    uploaded_by_user_id: str | None = None


def filename_from_storage_key(key: str) -> str:
    filename = posixpath.basename(unquote(key.strip("/")).replace("\\", "/"))
    return filename or "document.pdf"


def sidecar_key(doc_id: str) -> str:
    return f"{doc_id}/{SIDECAR_NAME}"


async def list_document_summaries() -> list[DocumentSummary]:
    """Return one row per uploaded doc_id, newest storage keys first."""
    from app.documents.ingest_work import read_document_meta

    storage = get_storage()
    objects = await storage.list()

    docs: dict[str, StoredObject] = {}
    for obj in objects:
        head, _, tail = obj.key.partition("/")
        if not tail:
            continue
        if tail in (SIDECAR_NAME, SYLLABUS_NAME):
            continue
        docs.setdefault(head, obj)

    results: list[DocumentSummary] = []
    for doc_id, obj in sorted(docs.items(), key=lambda item: item[1].key):
        meta = await read_document_meta(storage, doc_id)
        status: DocStatus = ingest_status_from_meta(meta)  # type: ignore[assignment]
        owner = meta.get("uploaded_by_user_id")
        results.append(
            DocumentSummary(
                doc_id=doc_id,
                key=obj.key,
                uri=obj.uri,
                filename=filename_from_storage_key(obj.key),
                status=status,
                syllabus_ready=bool(meta.get("syllabus_ready")),
                size=obj.size,
                content_type=obj.content_type,
                uploaded_by_user_id=owner if isinstance(owner, str) and owner else None,
            )
        )
    return results
