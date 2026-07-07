"""Tests for get_current_user dependency."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user, issue_token
from app.auth.store import UserStore
from app.config import get_settings

app = FastAPI()

_current_user_dep = Depends(get_current_user)


@app.get("/protected")
def protected(user=_current_user_dep) -> dict[str, str]:
    return {"id": user.id}


@pytest.fixture(autouse=True)
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_current_user_without_cookie_returns_401() -> None:
    client = TestClient(app)
    res = client.get("/protected")
    assert res.status_code == 401


def test_get_current_user_with_valid_cookie_returns_user() -> None:
    store = UserStore()
    user = store.upsert_google_user("sub-1", "a@example.com", "Alice")
    token = issue_token(
        user.id,
        email=user.email,
        name=user.name,
        google_sub=user.google_sub,
    )

    client = TestClient(app)
    settings = get_settings()
    client.cookies.set(settings.auth_cookie_name, token)
    res = client.get("/protected")
    assert res.status_code == 200
    assert res.json() == {"id": user.id}


def test_get_current_user_without_db_row_uses_jwt_claims() -> None:
    token = issue_token(
        "user-offline",
        email="offline@example.com",
        name="Offline",
        google_sub="sub-offline",
    )

    client = TestClient(app)
    settings = get_settings()
    client.cookies.set(settings.auth_cookie_name, token)
    res = client.get("/protected")
    assert res.status_code == 200
    assert res.json() == {"id": "user-offline"}
