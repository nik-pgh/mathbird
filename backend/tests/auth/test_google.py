"""Tests for Google OAuth helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.google import exchange_code_for_profile
from app.config import Settings


@pytest.mark.asyncio
async def test_exchange_code_normalizes_legacy_userinfo_id() -> None:
    settings = Settings(
        _env_file=None,
        google_client_id="client-id",
        google_client_secret="client-secret",
        oauth_redirect_url="http://localhost:8000/api/auth/google/callback",
    )

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "access-token"}

    userinfo_response = MagicMock()
    userinfo_response.raise_for_status = MagicMock()
    userinfo_response.json.return_value = {
        "id": "google-user-123",
        "email": "alice@example.com",
        "name": "Alice",
    }

    http = AsyncMock()
    http.post = AsyncMock(return_value=token_response)
    http.get = AsyncMock(return_value=userinfo_response)

    profile = await exchange_code_for_profile("auth-code", settings=settings, client=http)

    assert profile["sub"] == "google-user-123"
    assert profile["email"] == "alice@example.com"
