"""Google OAuth URL building and code exchange."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _require_oauth_config(settings: Settings) -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google OAuth is not configured")


def build_google_auth_url(state: str, *, settings: Settings | None = None) -> str:
    base = settings or get_settings()
    _require_oauth_config(base)
    params = {
        "client_id": base.google_client_id,
        "redirect_uri": base.oauth_redirect_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_profile(
    code: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    base = settings or get_settings()
    _require_oauth_config(base)

    token_payload = {
        "code": code,
        "client_id": base.google_client_id,
        "client_secret": base.google_client_secret,
        "redirect_uri": base.oauth_redirect_url,
        "grant_type": "authorization_code",
    }

    owns_client = client is None
    http = client or httpx.AsyncClient()
    try:
        token_res = await http.post(GOOGLE_TOKEN_URL, data=token_payload)
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise RuntimeError("Google token response missing access_token")

        user_res = await http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_res.raise_for_status()
        profile = user_res.json()
        if not profile.get("sub"):
            raise RuntimeError("Google profile missing sub")
        return profile
    finally:
        if owns_client:
            await http.aclose()
