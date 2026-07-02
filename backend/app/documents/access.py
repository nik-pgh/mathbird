"""Document ownership checks shared by HTTP routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from app.auth.store import User
from app.config import Settings, get_settings
from app.documents.catalog import DocumentSummary, sidecar_key
from app.storage.utils import open_storage_stream


async def read_document_meta(storage: Any, doc_id: str) -> dict[str, Any]:
    try:
        async with open_storage_stream(storage, sidecar_key(doc_id)) as handle:
            payload = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def user_can_access_doc(
    *,
    doc_id: str,
    user_id: str | None,
    meta: dict[str, Any],
    settings: Settings | None = None,
) -> bool:
    """Return whether ``user_id`` may read or mutate ``doc_id``."""
    settings = settings or get_settings()
    owner = meta.get("uploaded_by_user_id")
    if isinstance(owner, str) and owner:
        return user_id == owner
    if settings.legacy_doc_access == "allow":
        return user_id is not None
    return doc_id == settings.guest_sample_doc_id and bool(settings.guest_sample_doc_id)


def guest_can_access_doc(doc_id: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    sample = settings.guest_sample_doc_id
    return bool(sample) and doc_id == sample


async def assert_doc_access(storage: Any, doc_id: str, user: User) -> dict[str, Any]:
    meta = await read_document_meta(storage, doc_id)
    if user_can_access_doc(doc_id=doc_id, user_id=user.id, meta=meta):
        return meta
    raise HTTPException(status_code=403, detail="Document access denied.")


def filter_summaries_for_user(
    summaries: list[DocumentSummary],
    user: User,
    *,
    settings: Settings | None = None,
) -> list[DocumentSummary]:
    settings = settings or get_settings()
    visible: list[DocumentSummary] = []
    for summary in summaries:
        owner = summary.uploaded_by_user_id
        if owner and owner == user.id:
            visible.append(summary)
        elif not owner and settings.legacy_doc_access == "allow":
            visible.append(summary)
        elif not owner and summary.doc_id == settings.guest_sample_doc_id:
            visible.append(summary)
    return visible


async def resolve_token_doc_id(
    doc_id: str | None,
    *,
    user: User | None,
    is_guest: bool,
    storage: Any,
    settings: Settings | None = None,
) -> str | None:
    """Validate and resolve the active doc id embedded in a LiveKit token."""
    settings = settings or get_settings()

    if is_guest:
        if doc_id is None:
            return settings.guest_sample_doc_id or None
        if guest_can_access_doc(doc_id, settings):
            return doc_id
        raise HTTPException(status_code=403, detail="Document access denied.")

    if doc_id is None:
        return None

    meta = await read_document_meta(storage, doc_id)
    if user is None or not user_can_access_doc(
        doc_id=doc_id, user_id=user.id, meta=meta, settings=settings
    ):
        raise HTTPException(status_code=403, detail="Document access denied.")
    return doc_id
