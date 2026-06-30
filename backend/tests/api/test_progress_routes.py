"""Tests for progress REST routes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.auth import issue_token
from app.auth.store import UserStore
from app.config import get_settings
from app.progress.models import FocusPointer, ProblemProgress, ProgressState
from app.progress.store import get_progress_store, progress_key
from app.storage import base as storage_mod


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()


def _auth_clients() -> tuple[TestClient, TestClient, str, str]:
    user_a = UserStore().upsert_google_user("sub-a", "a@example.com", "A")
    user_b = UserStore().upsert_google_user("sub-b", "b@example.com", "B")
    client_a = TestClient(app)
    client_b = TestClient(app)
    settings = get_settings()
    client_a.cookies.set(settings.auth_cookie_name, issue_token(user_a.id))
    client_b.cookies.set(settings.auth_cookie_name, issue_token(user_b.id))
    return client_a, client_b, user_a.id, user_b.id


@pytest.mark.asyncio
async def test_get_progress_returns_saved_state(isolated_storage: Path) -> None:
    client_a, _client_b, user_a_id, _user_b_id = _auth_clients()
    doc_id = "doc-1"
    state = ProgressState(
        user_id=user_a_id,
        doc_id=doc_id,
        updated_at="2026-06-19T00:00:00+00:00",
        focus=FocusPointer(chapter_id="ch-1", concept_id="c-1", problem_id="p-1"),
        nodes={"p-1": ProblemProgress(level="practicing", attempts=1, updated_at="t")},
    )
    store = get_progress_store(storage_mod.get_storage())
    await store.save(state)

    res = client_a.get(f"/api/progress/{doc_id}")
    assert res.status_code == 200
    assert res.json()["focus"]["problem_id"] == "p-1"


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_progress(isolated_storage: Path) -> None:
    _client_a, client_b, user_a_id, _user_b_id = _auth_clients()
    doc_id = "doc-1"
    state = ProgressState(
        user_id=user_a_id,
        doc_id=doc_id,
        updated_at="2026-06-19T00:00:00+00:00",
    )
    await get_progress_store(storage_mod.get_storage()).save(state)

    res = client_b.get(f"/api/progress/{doc_id}")
    assert res.status_code == 404


def test_patch_progress_updates_focus(auth_client: TestClient, isolated_storage: Path) -> None:
    user = UserStore().upsert_google_user("sub-test", "t@example.com", "T")
    doc_id = "doc-1"
    path = isolated_storage / progress_key(user.id, doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "user_id": user.id,
                "doc_id": doc_id,
                "updated_at": "2026-06-19T00:00:00+00:00",
                "focus": None,
                "next_suggestion": None,
                "nodes": {},
            }
        ),
        encoding="utf-8",
    )

    res = auth_client.patch(
        f"/api/progress/{doc_id}",
        json={"focus": {"chapter_id": "ch-1", "concept_id": "c-1", "problem_id": "p-2"}},
    )
    assert res.status_code == 200
    assert res.json()["focus"]["problem_id"] == "p-2"
