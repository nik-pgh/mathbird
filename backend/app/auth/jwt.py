from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings, get_settings


@dataclass(frozen=True)
class SessionClaims:
    user_id: str
    email: str
    name: str
    google_sub: str


def issue_token(
    user_id: str,
    *,
    email: str = "",
    name: str = "",
    google_sub: str = "",
    settings: Settings | None = None,
) -> str:
    base = settings or get_settings()
    if not base.auth_jwt_secret:
        raise RuntimeError("AUTH_JWT_SECRET is not configured")
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "google_sub": google_sub,
        "iat": now,
        "exp": now + timedelta(hours=base.auth_jwt_expiry_hours),
    }
    return jwt.encode(payload, base.auth_jwt_secret, algorithm="HS256")


def decode_session(token: str, *, settings: Settings | None = None) -> SessionClaims:
    base = settings or get_settings()
    payload = jwt.decode(token, base.auth_jwt_secret, algorithms=["HS256"])
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise jwt.InvalidTokenError("missing sub")
    email = payload.get("email")
    name = payload.get("name")
    google_sub = payload.get("google_sub")
    return SessionClaims(
        user_id=sub,
        email=email if isinstance(email, str) else "",
        name=name if isinstance(name, str) else "",
        google_sub=google_sub if isinstance(google_sub, str) else "",
    )


def decode_token(token: str, *, settings: Settings | None = None) -> str:
    return decode_session(token, settings=settings).user_id
