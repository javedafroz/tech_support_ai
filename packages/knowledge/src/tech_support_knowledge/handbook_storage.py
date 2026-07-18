"""Ceph RGW object storage for Agent Handbooks (S3 API). No MinIO."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from tech_support_storage import ObjectStorage, StorageSettings, build_object_storage


@dataclass(frozen=True)
class HandbookStorageSettings:
    endpoint: str | None
    access_key: str | None
    secret_key: str | None
    bucket: str
    region: str
    backend: str = "s3"  # s3 (Ceph RGW) | memory
    addressing_style: str = "auto"  # auto | path | virtual

    @classmethod
    def from_env(cls) -> HandbookStorageSettings:
        return cls(
            endpoint=os.environ.get("CEPH_RGW_ENDPOINT"),
            access_key=os.environ.get("CEPH_RGW_ACCESS_KEY"),
            secret_key=os.environ.get("CEPH_RGW_SECRET_KEY"),
            bucket=os.environ.get("KB_HANDBOOK_S3_BUCKET", "agent-handbooks"),
            region=os.environ.get("CEPH_RGW_REGION", "us-east-1"),
            backend=os.environ.get("KB_HANDBOOK_STORAGE_BACKEND", "s3").lower(),
            addressing_style=os.environ.get("CEPH_RGW_ADDRESSING_STYLE", "auto").lower(),
        )

    def configuration_error(self) -> str | None:
        if self.backend == "memory":
            return None
        if not self.endpoint:
            return "CEPH_RGW_ENDPOINT is required for handbook storage"
        if not self.access_key or not self.secret_key:
            return "CEPH_RGW_ACCESS_KEY and CEPH_RGW_SECRET_KEY are required"
        return None

    def to_storage_settings(self) -> StorageSettings:
        return StorageSettings(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            bucket=self.bucket,
            region=self.region,
            backend=self.backend,
        )


@lru_cache
def get_handbook_storage() -> ObjectStorage:
    settings = HandbookStorageSettings.from_env()
    error = settings.configuration_error()
    if error:
        raise RuntimeError(error)
    style = None if settings.addressing_style == "auto" else settings.addressing_style
    return build_object_storage(settings.to_storage_settings(), addressing_style=style)


def reset_handbook_storage_cache() -> None:
    get_handbook_storage.cache_clear()


def handbook_object_key(
    *,
    org_id: str,
    document_id: str,
    version: int,
    filename: str,
) -> str:
    safe_name = filename.replace("\\", "/").split("/")[-1]
    return f"handbooks/{org_id}/{document_id}/v{version}/{safe_name}"
