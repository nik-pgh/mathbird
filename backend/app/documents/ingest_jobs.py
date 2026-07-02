"""In-process background PDF ingest tasks (v1 — single API process)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.documents.catalog import SIDECAR_NAME, SYLLABUS_NAME, ingest_status_from_meta
from app.documents.ingest_work import ingest_stored_pdf, read_document_meta, write_document_meta
from app.rag import get_retriever
from app.storage import StoredObject, get_storage

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

logger = logging.getLogger("mathbird.documents.ingest")

_inflight: set[str] = set()


def _find_stored_pdf(objects: list[StoredObject], doc_id: str) -> StoredObject | None:
    prefix = f"{doc_id}/"
    for obj in objects:
        if not obj.key.startswith(prefix):
            continue
        if obj.key.endswith(f"/{SIDECAR_NAME}") or obj.key.endswith(f"/{SYLLABUS_NAME}"):
            continue
        return obj
    return None


async def _run_ingest(doc_id: str) -> None:
    storage = get_storage()
    try:
        objects = await storage.list()
        stored = _find_stored_pdf(objects, doc_id)
        if stored is None:
            raise FileNotFoundError(doc_id)

        syllabus_ready, syllabus_error = await ingest_stored_pdf(
            storage,
            stored,
            doc_id=doc_id,
            retriever=get_retriever(),
        )
        existing = await read_document_meta(storage, doc_id)
        payload: dict[str, Any] = {
            **existing,
            "ingest_status": "indexed",
            "indexed": True,
            "indexed_at": datetime.now(UTC).isoformat(),
            "syllabus_ready": syllabus_ready,
        }
        payload.pop("ingest_error", None)
        if syllabus_error:
            payload["syllabus_error"] = syllabus_error
        await write_document_meta(storage, doc_id, payload)
    except Exception:
        logger.exception("Background ingest failed for doc_id=%s", doc_id)
        try:
            existing = await read_document_meta(storage, doc_id)
            await write_document_meta(
                storage,
                doc_id,
                {
                    **existing,
                    "ingest_status": "failed",
                    "ingest_error": "Document ingestion failed.",
                },
            )
        except Exception:
            logger.exception("Failed to persist ingest failure for doc_id=%s", doc_id)
    finally:
        _inflight.discard(doc_id)


def schedule_ingest(
    doc_id: str,
    *,
    background_tasks: BackgroundTasks | None = None,
) -> bool:
    """Start a background ingest unless one is already running. Returns False if busy."""
    if doc_id in _inflight:
        return False
    _inflight.add(doc_id)
    if background_tasks is not None:
        background_tasks.add_task(_run_ingest, doc_id)
        return True
    asyncio.create_task(_run_ingest(doc_id))
    return True


def is_ingest_running(doc_id: str) -> bool:
    return doc_id in _inflight


async def mark_ingesting(storage: Any, doc_id: str) -> dict[str, Any]:
    existing = await read_document_meta(storage, doc_id)
    payload = {
        **existing,
        "ingest_status": "ingesting",
        "ingest_started_at": datetime.now(UTC).isoformat(),
    }
    payload.pop("ingest_error", None)
    await write_document_meta(storage, doc_id, payload)
    return payload


async def reconcile_stuck_ingests() -> None:
    """Mark orphaned ``ingesting`` sidecars as failed so users can retry."""
    storage = get_storage()
    objects = await storage.list()
    doc_ids = {obj.key.partition("/")[0] for obj in objects if "/" in obj.key}
    for doc_id in doc_ids:
        if is_ingest_running(doc_id):
            continue
        meta = await read_document_meta(storage, doc_id)
        if ingest_status_from_meta(meta) != "ingesting":
            continue
        await write_document_meta(
            storage,
            doc_id,
            {
                **meta,
                "ingest_status": "failed",
                "ingest_error": "Ingest interrupted before completion. Retry indexing.",
            },
        )
