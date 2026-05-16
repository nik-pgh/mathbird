from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api.routes import documents
from app.storage import StoredObject


class FakeRetriever:
    def __init__(self, expected_bytes: bytes | None = None) -> None:
        self.expected_bytes = expected_bytes
        self.ingested_paths: list[str] = []
        self.ingested_doc_ids: list[str] = []
        self.path_existed_during_ingest = False

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:
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


def pdf_upload(data: bytes = b"%PDF-1.7\n") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename="book.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )


async def test_upload_document_ingests_local_file_uri_without_opening_storage(
    tmp_path,
    monkeypatch,
) -> None:
    local_pdf = tmp_path / "stored.pdf"
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
    assert retriever.ingested_paths == [str(local_pdf)]
    assert retriever.path_existed_during_ingest
    assert storage.opened_keys == []


async def test_upload_document_copies_non_file_storage_to_temp_pdf_for_ingestion(
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

    response = await documents.upload_document(pdf_upload(pdf_bytes))

    temp_path = Path(retriever.ingested_paths[0])
    assert response.uri == "s3://mathbird/doc-1/book.pdf"
    assert temp_path.suffix == ".pdf"
    assert retriever.path_existed_during_ingest
    assert not temp_path.exists()
    assert storage.opened_keys == ["doc-1/book.pdf"]
