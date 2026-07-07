"""Guest read access to the configured sample document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.rag import retriever as retriever_mod
from app.storage import base as storage_mod
from tests.api.conftest import make_auth_client, upload_pdf


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_PROVIDER", "null")
    monkeypatch.setenv("LEGACY_DOC_ACCESS", "deny")
    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "guest-sample")
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None
    yield tmp_path
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None


def _seed_guest_sample(storage_root: Path, *, filename: str = "sample.pdf") -> None:
    doc_dir = storage_root / "guest-sample"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / filename).write_bytes(b"%PDF-1.4\nsample\n")
    (doc_dir / "meta.json").write_text(
        json.dumps({"ingest_status": "indexed", "syllabus_ready": False}),
        encoding="utf-8",
    )


def test_guest_can_list_and_read_sample_doc(isolated_storage: Path) -> None:
    from app.api.main import app

    _seed_guest_sample(isolated_storage)
    client = TestClient(app)

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    docs = listing.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "guest-sample"

    file_res = client.get("/api/documents/guest-sample/file")
    assert file_res.status_code == 200
    assert file_res.content.startswith(b"%PDF")


def test_guest_cannot_list_without_config(
    isolated_storage: Path,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.main import app

    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "")
    get_settings.cache_clear()

    client = TestClient(app)
    assert client.get("/api/documents").status_code == 401


def test_guest_cannot_read_other_users_doc(
    isolated_storage: Path,
) -> None:
    from app.api.main import app

    _seed_guest_sample(isolated_storage)
    auth_client = make_auth_client("sub-owner", "owner@example.com")
    owned = upload_pdf(auth_client, name="private.pdf")
    guest_client = TestClient(app)

    listing = guest_client.get("/api/documents").json()["documents"]
    assert {d["doc_id"] for d in listing} == {"guest-sample"}

    assert guest_client.get(f"/api/documents/{owned['doc_id']}/file").status_code == 401


def test_guest_cannot_read_owned_sample_doc(isolated_storage: Path) -> None:
    from app.api.main import app

    doc_dir = isolated_storage / "guest-sample"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "sample.pdf").write_bytes(b"%PDF-1.4\nsample\n")
    (doc_dir / "meta.json").write_text(
        json.dumps(
            {
                "ingest_status": "indexed",
                "uploaded_by_user_id": "some-user",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    assert client.get("/api/documents").json()["documents"] == []
    assert client.get("/api/documents/guest-sample/file").status_code == 503
