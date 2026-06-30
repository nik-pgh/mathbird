"""List uploaded PDFs from storage (shared by HTTP API and console prompts)."""

import json
import posixpath
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import unquote

from app.storage import StoredObject, get_storage

DocStatus = Literal["uploaded", "indexed"]
SIDECAR_NAME = "meta.json"
SYLLABUS_NAME = "syllabus.json"


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


def filename_from_storage_key(key: str) -> str:
    filename = posixpath.basename(unquote(key.strip("/")).replace("\\", "/"))
    return filename or "document.pdf"


def sidecar_key(doc_id: str) -> str:
    return f"{doc_id}/{SIDECAR_NAME}"


async def _read_sidecar(storage: Any, doc_id: str) -> dict[str, Any]:
    try:
        async with storage.open(sidecar_key(doc_id)) as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


async def list_document_summaries() -> list[DocumentSummary]:
    """Return one row per uploaded doc_id, newest storage keys first."""
    storage = get_storage()
    objects = await storage.list()

    docs: dict[str, StoredObject] = {}
    sidecar_doc_ids: set[str] = set()
    for obj in objects:
        head, _, tail = obj.key.partition("/")
        if not tail:
            continue
        if tail == SIDECAR_NAME:
            sidecar_doc_ids.add(head)
            continue
        if tail == SYLLABUS_NAME:
            continue
        docs.setdefault(head, obj)

    results: list[DocumentSummary] = []
    for doc_id, obj in sorted(docs.items(), key=lambda item: item[1].key):
        status: DocStatus = "indexed" if doc_id in sidecar_doc_ids else "uploaded"
        meta = await _read_sidecar(storage, doc_id) if doc_id in sidecar_doc_ids else {}
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
            )
        )
    return results
