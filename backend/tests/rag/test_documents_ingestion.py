from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.api.routes import documents
from app.storage import StoredObject


class FakeRetriever:
    def __init__(self, expected_bytes: bytes | None = None, fail: bool = False) -> None:
        self.expected_bytes = expected_bytes
        self.fail = fail
        self.ingested_paths: list[str] = []
        self.ingested_doc_ids: list[str] = []
        self.path_existed_during_ingest = False

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:
        if self.fail:
            raise RuntimeError("parse failed")
        self.ingested_paths.append(path)
        self.ingested_doc_ids.append(doc_id)
        candidate = Path(path)
        self.path_existed_during_ingest = candidate.exists()
        if self.expected_bytes is not None:
            assert candidate.read_bytes() == self.expected_bytes


class FakeStorage:
    def __init__(self, *, stored: StoredObject, data: bytes) -> None:
        self.stored = stored
        self.data = data
        self.put_keys: list[str] = []
        self.opened_keys: list[str] = []
        self.deleted_keys: list[str] = []

    async def put(self, key, data, *, content_type):
        self.put_keys.append(key)
        return self.stored

    @asynccontextmanager
    async def open(self, key):
        self.opened_keys.append(key)
        stream = BytesIO(self.data)
        try:
            yield stream
        finally:
            stream.close()

    async def delete(self, key):
        self.deleted_keys.append(key)

    async def list(self):
        return [self.stored]


def pdf_upload(data: bytes = b"%PDF-1.7\n") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename="book.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )


async def test_upload_document_stores_pdf_without_ingesting(
    tmp_path,
    monkeypatch,
) -> None:
    local_pdf = tmp_path / "stored book.pdf"
    local_pdf.write_bytes(b"%PDF-1.7\nlocal")
    storage = FakeStorage(
        stored=StoredObject(
            key="doc-1/book.pdf",
            uri=local_pdf.as_uri(),
            size=local_pdf.stat().st_size,
            content_type="application/pdf",
        ),
        data=b"unused",
    )
    retriever = FakeRetriever()
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    monkeypatch.setattr(documents, "get_retriever", lambda: retriever)

    response = await documents.upload_document(pdf_upload())

    assert response.uri == local_pdf.as_uri()
    assert response.status == "uploaded"
    assert retriever.ingested_paths == []
    assert storage.opened_keys == []


async def test_ingest_document_uses_local_file_uri_without_opening_storage(
    tmp_path,
    monkeypatch,
) -> None:
    local_pdf = tmp_path / "stored book.pdf"
    local_pdf.write_bytes(b"%PDF-1.7\nlocal")
    storage = FakeStorage(
        stored=StoredObject(
            key="doc-1/book.pdf",
            uri=local_pdf.as_uri(),
            size=local_pdf.stat().st_size,
            content_type="application/pdf",
        ),
        data=b"unused",
    )
    retriever = FakeRetriever()
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    monkeypatch.setattr(documents, "get_retriever", lambda: retriever)

    response = await documents.ingest_document("doc-1")

    assert response.uri == local_pdf.as_uri()
    assert response.status == "indexed"
    assert retriever.ingested_paths == [str(local_pdf)]
    assert retriever.ingested_doc_ids == ["doc-1"]
    assert retriever.path_existed_during_ingest
    assert storage.opened_keys == []


async def test_ingest_document_copies_non_file_storage_to_temp_pdf_for_ingestion(
    monkeypatch,
) -> None:
    pdf_bytes = b"%PDF-1.7\nfrom s3"
    storage = FakeStorage(
        stored=StoredObject(
            key="doc-1/book.pdf",
            uri="s3://mathbird/doc-1/book.pdf",
            size=len(pdf_bytes),
            content_type="application/pdf",
        ),
        data=pdf_bytes,
    )
    retriever = FakeRetriever(expected_bytes=pdf_bytes)
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    monkeypatch.setattr(documents, "get_retriever", lambda: retriever)

    response = await documents.ingest_document("doc-1")

    temp_path = Path(retriever.ingested_paths[0])
    assert response.uri == "s3://mathbird/doc-1/book.pdf"
    assert response.status == "indexed"
    assert temp_path.name == "book.pdf"
    assert retriever.path_existed_during_ingest
    assert not temp_path.exists()
    assert storage.opened_keys == ["doc-1/book.pdf"]


async def test_ingest_document_sanitizes_encoded_separators_in_temp_filename(
    monkeypatch,
) -> None:
    pdf_bytes = b"%PDF-1.7\nencoded"
    storage = FakeStorage(
        stored=StoredObject(
            key="doc-1/%2e%2e%2fescape.pdf",
            uri="s3://mathbird/doc-1/%2e%2e%2fescape.pdf",
            size=len(pdf_bytes),
            content_type="application/pdf",
        ),
        data=pdf_bytes,
    )
    retriever = FakeRetriever(expected_bytes=pdf_bytes)
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    monkeypatch.setattr(documents, "get_retriever", lambda: retriever)

    await documents.ingest_document("doc-1")

    temp_path = Path(retriever.ingested_paths[0])
    assert temp_path.name == "escape.pdf"
    assert temp_path.parent.name != ".."
    assert not temp_path.exists()


async def test_ingest_document_preserves_stored_pdf_when_ingestion_fails(monkeypatch) -> None:
    storage = FakeStorage(
        stored=StoredObject(
            key="doc-1/book.pdf",
            uri="s3://mathbird/doc-1/book.pdf",
            size=12,
            content_type="application/pdf",
        ),
        data=b"%PDF-1.7\n",
    )
    retriever = FakeRetriever(fail=True)
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    monkeypatch.setattr(documents, "get_retriever", lambda: retriever)

    with pytest.raises(HTTPException) as exc_info:
        await documents.ingest_document("doc-1")

    assert exc_info.value.status_code == 502
    assert storage.deleted_keys == []
