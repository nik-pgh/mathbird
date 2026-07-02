"""Document ownership isolation across authenticated users."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from tests.api.conftest import make_auth_client, upload_pdf


def test_user_cannot_see_or_access_another_users_document(isolated_storage: Path) -> None:  # noqa: ARG001
    client_a = make_auth_client("sub-a", "a@example.com")
    client_b = make_auth_client("sub-b", "b@example.com")

    created = upload_pdf(client_a)
    doc_id = created["doc_id"]

    list_b = client_b.get("/api/documents").json()["documents"]
    assert doc_id not in {d["doc_id"] for d in list_b}

    assert client_b.post(f"/api/documents/{doc_id}/ingest").status_code == 403
    assert client_b.get(f"/api/documents/{doc_id}/file").status_code == 403
    assert client_b.get(f"/api/documents/{doc_id}/syllabus").status_code == 403
    assert client_b.post("/api/token", json={"doc_id": doc_id}).status_code == 403

    assert client_a.post("/api/token", json={"doc_id": doc_id}).status_code == 200


def test_legacy_doc_hidden_when_legacy_access_denied(isolated_storage: Path) -> None:
    legacy_id = "legacy-doc"
    (isolated_storage / legacy_id).mkdir(parents=True)
    (isolated_storage / legacy_id / "orphan.pdf").write_bytes(b"%PDF-1.4\n")

    client = make_auth_client("sub-legacy", "legacy@example.com")
    listing = client.get("/api/documents").json()["documents"]
    assert legacy_id not in {d["doc_id"] for d in listing}
    assert client.get(f"/api/documents/{legacy_id}/file").status_code == 403


def test_legacy_doc_visible_when_legacy_access_allowed(
    isolated_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEGACY_DOC_ACCESS", "allow")
    get_settings.cache_clear()

    legacy_id = "legacy-doc"
    (isolated_storage / legacy_id).mkdir(parents=True)
    (isolated_storage / legacy_id / "orphan.pdf").write_bytes(b"%PDF-1.4\n")

    client = make_auth_client("sub-legacy", "legacy@example.com")
    listing = client.get("/api/documents").json()["documents"]
    assert legacy_id in {d["doc_id"] for d in listing}
    assert client.get(f"/api/documents/{legacy_id}/file").status_code == 200
