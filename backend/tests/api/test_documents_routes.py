"""Tests for /api/documents routes (upload, ingest, list, file-stream)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings
from app.rag import retriever as retriever_mod
from app.storage import base as storage_mod


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point local storage at a fresh tmp dir and clear cached singletons."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_PROVIDER", "null")
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None
    yield tmp_path
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None


def _upload_pdf(client: TestClient, name: str = "doc.pdf") -> dict:
    return client.post(
        "/api/documents",
        files={"file": (name, io.BytesIO(b"%PDF-1.4\nstub\n"), "application/pdf")},
    ).json()


def test_uploaded_doc_status_uploaded_then_indexed(isolated_storage: Path) -> None:
    client = TestClient(app)

    created = _upload_pdf(client)
    assert created["status"] == "uploaded"
    doc_id = created["doc_id"]

    listing = client.get("/api/documents").json()
    statuses = {d["doc_id"]: d["status"] for d in listing["documents"]}
    assert statuses[doc_id] == "uploaded"

    ingest_res = client.post(f"/api/documents/{doc_id}/ingest")
    assert ingest_res.status_code == 200
    assert ingest_res.json()["status"] == "indexed"

    sidecar = isolated_storage / doc_id / "meta.json"
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    assert payload["indexed"] is True
    assert "indexed_at" in payload

    listing = client.get("/api/documents").json()
    statuses = {d["doc_id"]: d["status"] for d in listing["documents"]}
    assert statuses[doc_id] == "indexed"


def test_ingest_failure_preserves_file_and_502(
    isolated_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the retriever raises, ingest returns 502 but leaves the PDF in place
    so the user can retry via the Re-index path."""

    class _RaisingRetriever:
        async def retrieve(self, query, *, top_k=4, doc_ids=()):  # noqa: ARG002
            return []

        async def ingest_pdf(self, path, *, doc_id):  # noqa: ARG002
            raise RuntimeError("simulated ingest failure")

    monkeypatch.setattr(retriever_mod, "_singleton", _RaisingRetriever())

    client = TestClient(app)
    created = _upload_pdf(client)
    doc_id = created["doc_id"]
    pdf_path = isolated_storage / created["key"]
    assert pdf_path.exists()

    res = client.post(f"/api/documents/{doc_id}/ingest")
    assert res.status_code == 502

    # PDF remains for retry; sidecar never written.
    assert pdf_path.exists()
    assert not (isolated_storage / doc_id / "meta.json").exists()

    # Listing still surfaces the doc with status="uploaded".
    listing = client.get("/api/documents").json()
    statuses = {d["doc_id"]: d["status"] for d in listing["documents"]}
    assert statuses[doc_id] == "uploaded"
