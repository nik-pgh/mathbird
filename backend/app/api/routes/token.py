"""LiveKit access token issuance.

The frontend hits ``POST /api/token`` with a desired identity + room (and
optionally an ``active_doc_id``). The backend signs a short-lived JWT and
embeds the active doc id in the participant metadata so the agent worker
can scope retrieval to that PDF.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel, Field

from app.auth import User, get_optional_user
from app.config import get_settings
from app.documents.access import resolve_token_doc_id
from app.storage import get_storage

router = APIRouter()


class TokenRequest(BaseModel):
    identity: str | None = Field(
        default=None,
        description="Stable user identifier. If omitted, a random one is generated.",
    )
    room: str | None = Field(
        default=None,
        description="Room name. If omitted, a random one is generated.",
    )
    name: str | None = Field(default=None, description="Display name shown to others.")
    doc_id: str | None = Field(
        default=None,
        description="Active PDF doc_id for this session. Embedded in participant metadata.",
    )


class TokenResponse(BaseModel):
    token: str
    url: str
    room: str
    identity: str


@router.post("/token", response_model=TokenResponse)
async def create_token(
    req: TokenRequest,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> TokenResponse:
    settings = get_settings()
    if not (settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials are not configured on the server.",
        )

    is_guest = user is None
    if is_guest and not settings.guest_sample_doc_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Guest mode is not configured.",
        )

    identity = user.id if user else f"guest-{uuid.uuid4().hex[:8]}"
    room = req.room or f"room-{uuid.uuid4().hex[:8]}"

    builder = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(req.name or (user.name if user else "Guest") or identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )
    metadata: dict[str, str] = {}
    if user:
        metadata["user_id"] = user.id
    storage = get_storage()
    doc_id = await resolve_token_doc_id(
        req.doc_id,
        user=user,
        is_guest=is_guest,
        storage=storage,
        settings=settings,
    )
    if doc_id:
        metadata["active_doc_id"] = doc_id
    builder = builder.with_metadata(json.dumps(metadata))

    return TokenResponse(
        token=builder.to_jwt(),
        url=settings.livekit_url,
        room=room,
        identity=identity,
    )
