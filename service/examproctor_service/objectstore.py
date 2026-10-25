"""Evidence object store (S3-compatible). Browsers upload straight to it with presigned PUTs."""

import asyncio
import hashlib
from typing import Protocol

import boto3
from botocore.config import Config

from .config import Settings


class ObjectStore(Protocol):
    async def ensure_bucket(self) -> None: ...
    def presign_put(self, key: str, content_type: str, length: int, ttl_s: int) -> str: ...
    def presign_get(self, key: str, ttl_s: int) -> str: ...
    async def sha256_of(self, key: str) -> tuple[str, int] | None: ...
    async def delete_prefix(self, prefix: str) -> int: ...
    async def get_bytes(self, key: str) -> bytes | None: ...
    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...


class S3ObjectStore:
    """boto3 is synchronous; network calls run in a thread. Presigning is local and cheap."""

    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.evidence_bucket
        session = boto3.session.Session()
        common = dict(
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key,
            region_name=settings.object_store_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.client = session.client("s3", endpoint_url=settings.object_store_url, **common)
        # Browsers reach the store on a different host name than the service does.
        self.public = session.client("s3", endpoint_url=settings.object_store_public_url, **common)

    async def ensure_bucket(self) -> None:
        def run() -> None:
            existing = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
            if self.bucket not in existing:
                self.client.create_bucket(Bucket=self.bucket)

        await asyncio.to_thread(run)

    def presign_put(self, key: str, content_type: str, length: int, ttl_s: int) -> str:
        return self.public.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": length,
            },
            ExpiresIn=ttl_s,
        )

    def presign_get(self, key: str, ttl_s: int) -> str:
        """Short-lived read link for a reviewer's browser."""
        return self.public.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=ttl_s
        )

    async def sha256_of(self, key: str) -> tuple[str, int] | None:
        def run() -> tuple[str, int] | None:
            try:
                body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            except self.client.exceptions.NoSuchKey:
                return None
            return hashlib.sha256(body).hexdigest(), len(body)

        return await asyncio.to_thread(run)

    async def get_bytes(self, key: str) -> bytes | None:
        def run() -> bytes | None:
            try:
                return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            except self.client.exceptions.NoSuchKey:
                return None

        return await asyncio.to_thread(run)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            lambda: self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        )

    async def delete_prefix(self, prefix: str) -> int:
        def run() -> int:
            deleted = 0
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if keys:
                    self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})
                    deleted += len(keys)
            return deleted

        return await asyncio.to_thread(run)


class MemoryObjectStore:
    """Test double: `put` simulates the browser's presigned upload."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def ensure_bucket(self) -> None:
        return None

    def presign_put(self, key: str, content_type: str, length: int, ttl_s: int) -> str:
        return f"memory://evidence/{key}?ttl={ttl_s}"

    def presign_get(self, key: str, ttl_s: int) -> str:
        return f"memory://evidence/{key}?get&ttl={ttl_s}"

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def sha256_of(self, key: str) -> tuple[str, int] | None:
        data = self.objects.get(key)
        return None if data is None else (hashlib.sha256(data).hexdigest(), len(data))

    async def get_bytes(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def delete_prefix(self, prefix: str) -> int:
        keys = [k for k in self.objects if k.startswith(prefix)]
        for k in keys:
            del self.objects[k]
        return len(keys)
