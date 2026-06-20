"""Shared fixtures for authenticated API route tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import issue_token
from app.auth.store import UserStore
from app.config import get_settings


@pytest.fixture
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def auth_client(auth_env: None) -> TestClient:
    from app.api.main import app

    user = UserStore().upsert_google_user("sub-test", "test@example.com", "Test User")
    token = issue_token(user.id)
    client = TestClient(app)
    client.cookies.set(get_settings().auth_cookie_name, token)
    return client
