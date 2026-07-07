"""FastAPI dependencies for authenticated routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth.jwt import decode_session
from app.auth.store import User, get_user_store
from app.config import get_settings


def _user_from_session(token: str) -> User:
    claims = decode_session(token)
    user = get_user_store().get_by_id(claims.user_id)
    if user is not None:
        return user
    if not claims.email:
        raise HTTPException(status_code=401, detail="User not found")
    # Stateless fallback: JWT carries profile claims when the local SQLite row
    # is missing (e.g. another Fly machine handled OAuth, or the DB was wiped).
    return User(
        id=claims.user_id,
        google_sub=claims.google_sub,
        email=claims.email,
        name=claims.name or claims.email,
        created_at="",
    )


def get_current_user(request: Request) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        return _user_from_session(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


def get_optional_user(request: Request) -> User | None:
    """Return the authenticated user, or None for guest sessions.

    Unlike get_current_user, this never raises 401 — it silently
    returns None when no valid session cookie is present. Use it
    on routes that should work for both logged-in and guest users
    (e.g. token issuance for guest voice sessions).
    """
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    try:
        return _user_from_session(token)
    except Exception:
        return None
