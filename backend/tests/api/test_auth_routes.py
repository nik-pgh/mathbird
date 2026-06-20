"""Tests for /api/auth routes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings


@pytest.fixture(autouse=True)
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URL", "http://testserver/api/auth/google/callback")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_google_login_redirects_when_configured() -> None:
    client = TestClient(app)
    res = client.get("/api/auth/google", follow_redirects=False)
    assert res.status_code == 302
    assert "accounts.google.com" in res.headers["location"]
    assert "mathbird_oauth_state" in res.cookies


def test_google_login_503_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    client = TestClient(app)
    res = client.get("/api/auth/google")
    assert res.status_code == 503


@patch("app.api.routes.auth.exchange_code_for_profile", new_callable=AsyncMock)
def test_google_callback_sets_session_cookie(mock_exchange: AsyncMock) -> None:
    mock_exchange.return_value = {
        "sub": "google-sub-1",
        "email": "alice@example.com",
        "name": "Alice",
    }
    client = TestClient(app)
    login = client.get("/api/auth/google", follow_redirects=False)
    state = login.cookies.get("mathbird_oauth_state")

    res = client.get(
        f"/api/auth/google/callback?code=fake-code&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 302
    settings = get_settings()
    assert settings.auth_cookie_name in res.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"


def test_logout_clears_cookie() -> None:
    client = TestClient(app)
    with patch("app.api.routes.auth.exchange_code_for_profile", new_callable=AsyncMock) as mock_exchange:
        mock_exchange.return_value = {
            "sub": "google-sub-2",
            "email": "bob@example.com",
            "name": "Bob",
        }
        login = client.get("/api/auth/google", follow_redirects=False)
        state = login.cookies.get("mathbird_oauth_state")
        client.get(f"/api/auth/google/callback?code=code&state={state}")

    res = client.post("/api/auth/logout")
    assert res.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 401
