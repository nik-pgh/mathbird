from __future__ import annotations

from io import BytesIO

from app.storage.s3 import S3Storage


class CloseTrackingBody(BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.close_called = False

    def close(self) -> None:
        self.close_called = True
        super().close()


class FakeS3Client:
    def __init__(self, body: CloseTrackingBody) -> None:
        self.body = body
        self.get_object_calls: list[dict[str, str]] = []
        self.download_fileobj_called = False

    def get_object(self, **kwargs):
        self.get_object_calls.append(kwargs)
        return {"Body": self.body}

    def download_fileobj(self, *args, **kwargs) -> None:
        self.download_fileobj_called = True
        raise AssertionError("S3Storage.open should stream get_object Body")


async def test_s3_open_streams_get_object_body_and_closes_it() -> None:
    body = CloseTrackingBody(b"%PDF-1.7\n")
    client = FakeS3Client(body)
    storage = object.__new__(S3Storage)
    storage.bucket = "mathbird"
    storage.client = client

    async with storage.open("doc-1/book.pdf") as stream:
        assert stream.read() == b"%PDF-1.7\n"

    assert client.get_object_calls == [{"Bucket": "mathbird", "Key": "doc-1/book.pdf"}]
    assert not client.download_fileobj_called
    assert body.close_called
