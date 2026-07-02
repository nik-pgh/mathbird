"""AWS S3 storage backend.

Stubbed but functional. Set ``STORAGE_BACKEND=s3`` and the required env vars
to use it. Requires the ``boto3`` extra (already in pyproject.toml).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import BinaryIO

from .base import StoredObject


class S3Storage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET must be set when using the s3 storage backend")

        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def _put_sync(self, key: str, data: BinaryIO, *, content_type: str) -> StoredObject:
        self.client.upload_fileobj(
            data,
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return StoredObject(
            key=key,
            uri=f"s3://{self.bucket}/{key}",
            size=head["ContentLength"],
            content_type=head.get("ContentType", content_type),
        )

    async def put(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str,
    ) -> StoredObject:
        return await asyncio.to_thread(self._put_sync, key, data, content_type=content_type)

    @asynccontextmanager
    async def open(self, key: str) -> AsyncIterator[BinaryIO]:
        def _get_object() -> BinaryIO:
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
            except self.client.exceptions.NoSuchKey as err:  # pragma: no cover
                raise FileNotFoundError(key) from err
            return response["Body"]

        body = await asyncio.to_thread(_get_object)
        try:
            yield body
        finally:
            await asyncio.to_thread(body.close)

    def _list_sync(self, prefix: str) -> list[StoredObject]:
        paginator = self.client.get_paginator("list_objects_v2")
        results: list[StoredObject] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                results.append(
                    StoredObject(
                        key=obj["Key"],
                        uri=f"s3://{self.bucket}/{obj['Key']}",
                        size=obj["Size"],
                        content_type="application/octet-stream",
                    )
                )
        return results

    async def list(self, prefix: str = "") -> list[StoredObject]:
        return await asyncio.to_thread(self._list_sync, prefix)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)
