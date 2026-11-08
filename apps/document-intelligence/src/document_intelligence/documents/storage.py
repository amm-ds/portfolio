"""Blob storage protocol with local and S3-compatible implementations."""

import os
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

_SAFE_KEY = re.compile(r"^[a-zA-Z0-9_./-]+$")


class BlobNotFoundError(FileNotFoundError):
    pass


class BlobStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


def validate_key(key: str) -> None:
    if not _SAFE_KEY.fullmatch(key) or ".." in key.split("/") or key.startswith("/"):
        raise ValueError("Unsafe blob key")


class LocalBlobStore:
    """Atomic local writes; keys remain relative to the configured root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Blob key escapes storage root")
        return path

    def put(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.{uuid4().hex}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise BlobNotFoundError(key) from exc


class S3BlobStore:
    """Small S3 adapter; credentials come from the standard AWS provider chain."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "documents",
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    def _key(self, key: str) -> str:
        validate_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key: str, content: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=content)

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            return bytes(response["Body"].read())
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise BlobNotFoundError(key) from exc
            raise
