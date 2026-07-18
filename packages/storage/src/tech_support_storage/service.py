from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class StorageSettings:
    endpoint: str | None
    access_key: str | None
    secret_key: str | None
    bucket: str
    region: str
    backend: str = "s3"

    @classmethod
    def from_env(cls) -> StorageSettings:
        return cls(
            endpoint=os.environ.get("S3_ENDPOINT"),
            access_key=os.environ.get("S3_ACCESS_KEY"),
            secret_key=os.environ.get("S3_SECRET_KEY"),
            bucket=os.environ.get("S3_BUCKET", "attachments"),
            region=os.environ.get("S3_REGION", "us-east-1"),
            backend=os.environ.get("STORAGE_BACKEND", "s3").lower(),
        )


class ObjectStorage(Protocol):
    def put_object(self, *, key: str, data: bytes, content_type: str) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...


class MemoryStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put_object(self, *, key: str, data: bytes, content_type: str) -> None:
        del content_type
        self._objects[key] = data

    def get_object(self, key: str) -> bytes:
        if key not in self._objects:
            raise FileNotFoundError(key)
        return self._objects[key]

    def delete_object(self, key: str) -> None:
        self._objects.pop(key, None)


class S3Storage:
    def __init__(
        self,
        settings: StorageSettings,
        *,
        addressing_style: str | None = None,
    ) -> None:
        self._settings = settings
        client_kwargs: dict = {
            "endpoint_url": settings.endpoint,
            "aws_access_key_id": settings.access_key,
            "aws_secret_access_key": settings.secret_key,
            "region_name": settings.region,
        }
        if addressing_style and addressing_style != "auto":
            from botocore.config import Config

            client_kwargs["config"] = Config(s3={"addressing_style": addressing_style})
        self._client: BaseClient = boto3.client("s3", **client_kwargs)

    def put_object(self, *, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._settings.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_object(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._settings.bucket, Key=key)
        except ClientError as exc:
            raise FileNotFoundError(key) from exc
        return response["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._settings.bucket, Key=key)


# Backwards-compatible aliases
_MemoryStorage = MemoryStorage
_S3Storage = S3Storage


def build_object_storage(
    settings: StorageSettings,
    *,
    addressing_style: str | None = None,
) -> ObjectStorage:
    if settings.backend == "memory":
        return MemoryStorage()
    return S3Storage(settings, addressing_style=addressing_style)


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = StorageSettings.from_env()
    return build_object_storage(settings)


def reset_object_storage_cache() -> None:
    get_object_storage.cache_clear()
