"""Student progress REST endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.auth import User, get_current_user
from app.documents.access import assert_doc_access
from app.progress import FocusPointer, ProgressState, get_progress_store
from app.storage import get_storage

router = APIRouter()


class ProgressPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: FocusPointer


@router.get("/progress/{doc_id}", response_model=ProgressState)
async def get_progress(
    doc_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> ProgressState:
    store = get_progress_store(get_storage())
    storage = get_storage()
    await assert_doc_access(storage, doc_id, user)
    state = await store.load(user.id, doc_id)
    if state is None or state.user_id != user.id:
        raise HTTPException(status_code=404, detail="Progress not found.")
    return state


@router.patch("/progress/{doc_id}", response_model=ProgressState)
async def patch_progress(
    doc_id: str,
    body: ProgressPatchRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> ProgressState:
    store = get_progress_store(get_storage())
    storage = get_storage()
    await assert_doc_access(storage, doc_id, user)
    state = await store.load(user.id, doc_id)
    if state is None:
        state = ProgressState(
            user_id=user.id,
            doc_id=doc_id,
            updated_at=datetime.now(UTC).isoformat(),
        )
    elif state.user_id != user.id:
        raise HTTPException(status_code=404, detail="Progress not found.")

    state.focus = body.focus
    state.updated_at = datetime.now(UTC).isoformat()
    await store.save(state)
    return state
