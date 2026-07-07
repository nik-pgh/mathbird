from __future__ import annotations

from pathlib import Path

import pytest

from app.auth.store import UserStore, stable_user_id
from app.config import get_settings


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UserStore:
    db = tmp_path / "auth.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(db))
    get_settings.cache_clear()
    yield UserStore()
    get_settings.cache_clear()


def test_upsert_google_user_creates_then_updates(store: UserStore) -> None:
    u1 = store.upsert_google_user("sub-1", "a@example.com", "Alice")
    assert u1.id == stable_user_id("sub-1")
    assert u1.email == "a@example.com"
    u2 = store.upsert_google_user("sub-1", "a@example.com", "Alice Smith")
    assert u2.id == u1.id
    assert u2.name == "Alice Smith"
    assert store.get_by_id(u1.id) is not None
