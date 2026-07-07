"""Shared fixtures for authenticated API route tests."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import issue_token
from app.auth.store import get_user_store
from app.config import get_settings
from app.rag import retriever as retriever_mod
from app.storage import base as storage_mod


@pytest.fixture
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    get_settings.cache_clear()
    get_user_store.cache_clear()
    yield
    get_settings.cache_clear()
    get_user_store.cache_clear()


@pytest.fixture
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Fresh local storage + null RAG for document route tests."""
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_PROVIDER", "null")
    monkeypatch.setenv("LEGACY_DOC_ACCESS", "deny")
    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "x" * 32)
    get_settings.cache_clear()
    get_user_store.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None
    yield tmp_path
    get_settings.cache_clear()
    get_user_store.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None


@pytest.fixture
def auth_client(auth_env: None) -> TestClient:
    from app.api.main import app

    user = get_user_store().upsert_google_user("sub-test", "test@example.com", "Test User")
    token = issue_token(user.id)
    client = TestClient(app)
    client.cookies.set(get_settings().auth_cookie_name, token)
    return client


def make_auth_client(google_sub: str, email: str, *, name: str | None = None) -> TestClient:
    from app.api.main import app

    user = get_user_store().upsert_google_user(google_sub, email, name or email.split("@")[0])
    token = issue_token(user.id)
    client = TestClient(app)
    client.cookies.set(get_settings().auth_cookie_name, token)
    return client


def upload_pdf(client: TestClient, name: str = "doc.pdf") -> dict:
    return client.post(
        "/api/documents",
        files={"file": (name, io.BytesIO(b"%PDF-1.4\nstub\n"), "application/pdf")},
    ).json()


def seed_owned_doc(
    storage_root: Path, doc_id: str, user_id: str, *, filename: str = "doc.pdf"
) -> None:
    doc_dir = storage_root / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / filename).write_bytes(b"%PDF-1.4\nstub\n")
    (doc_dir / "meta.json").write_text(
        json.dumps({"uploaded_by_user_id": user_id}),
        encoding="utf-8",
    )
