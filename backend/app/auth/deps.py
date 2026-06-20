"""FastAPI dependencies for authenticated routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth.jwt import decode_token
from app.auth.store import User, UserStore
from app.config import get_settings


def get_current_user(request: Request) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    user = UserStore().get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
