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

from app.auth import User, get_current_user
from app.config import get_settings

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
    user: Annotated[User, Depends(get_current_user)],
) -> TokenResponse:
    settings = get_settings()
    if not (settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials are not configured on the server.",
        )

    identity = user.id
    room = req.room or f"room-{uuid.uuid4().hex[:8]}"

    builder = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(req.name or user.name or identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )
    metadata: dict[str, str] = {"user_id": user.id}
    if req.doc_id:
        metadata["active_doc_id"] = req.doc_id
    builder = builder.with_metadata(json.dumps(metadata))

    return TokenResponse(
        token=builder.to_jwt(),
        url=settings.livekit_url,
        room=room,
        identity=identity,
    )
