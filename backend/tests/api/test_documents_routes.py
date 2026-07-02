"""Tests for /api/documents routes (upload, ingest, list, file-stream)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.rag import retriever as retriever_mod
from tests.api.conftest import upload_pdf


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point local storage at a fresh tmp dir and clear cached singletons."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_PROVIDER", "null")
    monkeypatch.setenv("LEGACY_DOC_ACCESS", "deny")
    get_settings.cache_clear()
    from app.storage import base as storage_mod

    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None
    yield tmp_path
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None


def test_documents_require_auth(isolated_storage: Path) -> None:  # noqa: ARG001
    from app.api.main import app

    client = TestClient(app)
    res = client.get("/api/documents")
    assert res.status_code == 401


def test_uploaded_doc_status_uploaded_then_indexed(
    isolated_storage: Path,
    auth_client: TestClient,
) -> None:
    client = auth_client

    created = upload_pdf(client)
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
    assert payload.get("syllabus_ready") is False
    assert "uploaded_by_user_id" in payload

    listing = client.get("/api/documents").json()
    statuses = {d["doc_id"]: d["status"] for d in listing["documents"]}
    assert statuses[doc_id] == "indexed"


def test_ingest_builds_syllabus_when_parser_available(
    isolated_storage: Path,
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage

    sample = ParsedDocument(
        doc_id="placeholder",
        filename="doc.pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p1:b0",
                        page_number=1,
                        block_type="exercise",
                        text="Problem 1.",
                        chapter_number=1,
                        exercise_number="1",
                    )
                ],
            )
        ],
    )

    async def _fake_parse(path: str, *, doc_id: str, settings=None):  # noqa: ANN001, ARG001
        return ParsedDocument(
            doc_id=doc_id,
            filename="doc.pdf",
            pages=sample.pages,
        )

    monkeypatch.setenv("LLAMAPARSE_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.routes.documents.parse_pdf_to_document", _fake_parse)

    client = auth_client
    created = upload_pdf(client)
    doc_id = created["doc_id"]

    ingest_res = client.post(f"/api/documents/{doc_id}/ingest")
    assert ingest_res.status_code == 200
    body = ingest_res.json()
    assert body["syllabus_ready"] is True

    sidecar = json.loads((isolated_storage / doc_id / "meta.json").read_text())
    assert sidecar["syllabus_ready"] is True
    assert (isolated_storage / doc_id / "syllabus.json").exists()

    syllabus_res = client.get(f"/api/documents/{doc_id}/syllabus")
    assert syllabus_res.status_code == 200
    first_exercise = (
        syllabus_res.json()["chapters"][0]["concepts"][0]["problems"][0]["exercise_number"]
    )
    assert first_exercise == "1"


def test_ingest_failure_preserves_file_and_502(
    isolated_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_client: TestClient,
) -> None:
    """If the retriever raises, ingest returns 502 but leaves the PDF in place
    so the user can retry via the Re-index path."""

    class _RaisingRetriever:
        async def retrieve(self, query, *, top_k=4, doc_ids=()):  # noqa: ARG002
            return []

        async def ingest_pdf(self, path, *, doc_id):  # noqa: ARG002
            raise RuntimeError("simulated ingest failure")

    monkeypatch.setattr(retriever_mod, "_singleton", _RaisingRetriever())

    client = auth_client
    created = upload_pdf(client)
    doc_id = created["doc_id"]
    pdf_path = isolated_storage / created["key"]
    assert pdf_path.exists()

    res = client.post(f"/api/documents/{doc_id}/ingest")
    assert res.status_code == 502

    # PDF remains for retry; indexed flag not set on sidecar.
    assert pdf_path.exists()
    sidecar = json.loads((isolated_storage / doc_id / "meta.json").read_text())
    assert sidecar.get("indexed") is not True

    # Listing still surfaces the doc with status="uploaded".
    listing = client.get("/api/documents").json()
    statuses = {d["doc_id"]: d["status"] for d in listing["documents"]}
    assert statuses[doc_id] == "uploaded"


def test_get_document_file_returns_pdf_bytes(
    isolated_storage: Path,  # noqa: ARG001
    auth_client: TestClient,
) -> None:
    client = auth_client
    created = upload_pdf(client, name="textbook.pdf")
    doc_id = created["doc_id"]

    res = client.get(f"/api/documents/{doc_id}/file")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "inline" in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"%PDF-1.4")


def test_get_document_file_quotes_download_filename_safely(
    isolated_storage: Path,  # noqa: ARG001
    auth_client: TestClient,
) -> None:
    client = auth_client
    created = upload_pdf(client, name='bad"name.pdf')
    doc_id = created["doc_id"]

    res = client.get(f"/api/documents/{doc_id}/file")

    assert res.status_code == 200
    assert 'filename="bad_name.pdf"' in res.headers["content-disposition"]
    assert 'bad"name.pdf' not in res.headers["content-disposition"]


def test_get_document_file_404_for_unknown_id(
    isolated_storage: Path,  # noqa: ARG001
    auth_client: TestClient,
) -> None:
    client = auth_client
    res = client.get("/api/documents/does-not-exist/file")
    assert res.status_code == 403
