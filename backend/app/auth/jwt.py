from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings, get_settings


def issue_token(user_id: str, *, settings: Settings | None = None) -> str:
    base = settings or get_settings()
    if not base.auth_jwt_secret:
        raise RuntimeError("AUTH_JWT_SECRET is not configured")
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=base.auth_jwt_expiry_hours),
    }
    return jwt.encode(payload, base.auth_jwt_secret, algorithm="HS256")


def decode_token(token: str, *, settings: Settings | None = None) -> str:
    base = settings or get_settings()
    payload = jwt.decode(token, base.auth_jwt_secret, algorithms=["HS256"])
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise jwt.InvalidTokenError("missing sub")
    return sub
