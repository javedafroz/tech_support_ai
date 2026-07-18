"""Admin KB document lifecycle — upload, ingest, publish, reindex."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_knowledge.embeddings import get_embedder
from tech_support_knowledge.handbook_storage import (
    get_handbook_storage,
    handbook_object_key,
    reset_handbook_storage_cache,
)
from tech_support_knowledge.ingest import ingest_document, slugify
from tech_support_knowledge.store import get_knowledge_settings, get_knowledge_store

from tech_support_api.config import Settings, get_settings
from tech_support_api.db.models import KbDocument, KbIngestJob
from tech_support_api.dependencies.keycloak_auth import AdminPrincipal

logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "text/plain": ".md",
}


def _sync_handbook_env(settings: Settings) -> None:
    """Push API settings into env so knowledge package factories see them."""
    os.environ["KB_HANDBOOK_S3_BUCKET"] = settings.kb_handbook_s3_bucket
    os.environ["KB_HANDBOOK_STORAGE_BACKEND"] = settings.kb_handbook_storage_backend
    if settings.ceph_rgw_endpoint:
        os.environ["CEPH_RGW_ENDPOINT"] = settings.ceph_rgw_endpoint
    if settings.ceph_rgw_access_key:
        os.environ["CEPH_RGW_ACCESS_KEY"] = settings.ceph_rgw_access_key
    if settings.ceph_rgw_secret_key:
        os.environ["CEPH_RGW_SECRET_KEY"] = settings.ceph_rgw_secret_key
    os.environ["CEPH_RGW_REGION"] = settings.ceph_rgw_region
    os.environ["CEPH_RGW_ADDRESSING_STYLE"] = settings.ceph_rgw_addressing_style
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
    reset_handbook_storage_cache()


def _guess_content_type(filename: str, content_type: str | None) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".md") or name.endswith(".markdown"):
        return "text/markdown"
    if content_type and content_type.split(";")[0].strip().lower() in _ALLOWED_TYPES:
        return content_type.split(";")[0].strip().lower()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Upload PDF or Markdown (.md).",
    )


def _actor_label(principal: AdminPrincipal) -> str:
    return principal.username or principal.email or principal.subject


class KbService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        _sync_handbook_env(self._settings)

    async def create_from_upload(
        self,
        *,
        principal: AdminPrincipal,
        file: UploadFile,
        title: str | None,
        org_id: str | None,
        category_tags: list[str] | None,
        auto_ingest: bool = True,
    ) -> KbDocument:
        filename = file.filename or "handbook.bin"
        content_type = _guess_content_type(filename, file.content_type)
        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {_MAX_UPLOAD_BYTES} bytes",
            )

        doc_id = uuid4()
        org = (org_id or "default").strip() or "default"
        resolved_title = (title or re.sub(r"\.[^.]+$", "", filename)).strip() or "Untitled handbook"
        slug = await self._unique_slug(org, slugify(resolved_title))
        version = 1
        object_key = handbook_object_key(
            org_id=org,
            document_id=str(doc_id),
            version=version,
            filename=filename,
        )

        storage = get_handbook_storage()
        storage.put_object(key=object_key, data=data, content_type=content_type)

        doc = KbDocument(
            id=doc_id,
            org_id=org,
            title=resolved_title,
            slug=slug,
            status="draft",
            category_tags=list(category_tags or []),
            source_content_type=content_type,
            object_key=object_key,
            version=version,
            created_by=_actor_label(principal),
            updated_by=_actor_label(principal),
        )
        self._db.add(doc)
        await self._db.flush()

        if auto_ingest:
            await self._run_ingest(doc, principal=principal, publish=False)

        await self._db.commit()
        await self._db.refresh(doc)
        return doc

    async def get_document(self, document_id: UUID) -> KbDocument:
        doc = await self._db.get(KbDocument, document_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return doc

    async def update_document(
        self,
        document_id: UUID,
        *,
        principal: AdminPrincipal,
        title: str | None = None,
        category_tags: list[str] | None = None,
        status: str | None = None,
    ) -> KbDocument:
        doc = await self.get_document(document_id)
        if title is not None:
            doc.title = title.strip() or doc.title
        if category_tags is not None:
            doc.category_tags = list(category_tags)
        if status is not None:
            if status not in {"draft", "published", "archived"}:
                raise HTTPException(status_code=400, detail="Invalid status")
            if status == "published" and not principal.can_publish:
                raise HTTPException(status_code=403, detail="Publish requires kb_admin")
            if status == "published":
                await self._publish(doc, principal=principal)
            elif status == "archived":
                get_knowledge_store().delete_by_document(doc.id)
                doc.status = "archived"
                doc.updated_by = _actor_label(principal)
            else:
                if doc.chunk_count and doc.chunk_count > 0:
                    try:
                        get_knowledge_store().set_document_status(doc.id, "draft")
                    except Exception:
                        logger.warning(
                            "Failed to unpublish chunks for %s", doc.id, exc_info=True
                        )
                doc.status = "draft"
                doc.published_at = None
                doc.updated_by = _actor_label(principal)
        else:
            doc.updated_by = _actor_label(principal)
        await self._db.commit()
        await self._db.refresh(doc)
        return doc

    async def publish(self, document_id: UUID, *, principal: AdminPrincipal) -> KbDocument:
        if not principal.can_publish:
            raise HTTPException(status_code=403, detail="Publish requires kb_admin")
        doc = await self.get_document(document_id)
        await self._publish(doc, principal=principal)
        await self._db.commit()
        await self._db.refresh(doc)
        return doc

    async def _publish(self, doc: KbDocument, *, principal: AdminPrincipal) -> KbIngestJob:
        """Publish without re-embedding when chunks already exist.

        Flips the vector-store payload status to ``published`` in place. Falls
        back to a full ingest only if the document has never been indexed (or
        its chunks are missing from the vector store).
        """
        updated = 0
        if doc.chunk_count and doc.chunk_count > 0:
            try:
                updated = get_knowledge_store().set_document_status(doc.id, "published")
            except Exception:
                logger.warning("Fast publish failed for %s; falling back to ingest", doc.id, exc_info=True)
                updated = 0

        if updated <= 0:
            return await self._run_ingest(doc, principal=principal, publish=True)

        doc.status = "published"
        doc.published_at = datetime.now(UTC)
        doc.updated_by = _actor_label(principal)
        job = KbIngestJob(id=uuid4(), document_id=doc.id, status="succeeded")
        job.started_at = datetime.now(UTC)
        job.finished_at = datetime.now(UTC)
        self._db.add(job)
        await self._db.flush()
        return job

    async def reindex(self, document_id: UUID, *, principal: AdminPrincipal) -> KbIngestJob:
        doc = await self.get_document(document_id)
        job = await self._run_ingest(
            doc,
            principal=principal,
            publish=doc.status == "published",
        )
        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def delete_document(self, document_id: UUID, *, principal: AdminPrincipal) -> None:
        if not principal.can_publish:
            raise HTTPException(status_code=403, detail="Delete requires kb_admin")
        doc = await self.get_document(document_id)
        get_knowledge_store().delete_by_document(doc.id)
        storage = get_handbook_storage()
        try:
            storage.delete_object(doc.object_key)
        except Exception:
            logger.warning("Failed to delete source object %s", doc.object_key, exc_info=True)
        if doc.derived_markdown_object_key:
            try:
                storage.delete_object(doc.derived_markdown_object_key)
            except Exception:
                logger.warning(
                    "Failed to delete derived markdown %s",
                    doc.derived_markdown_object_key,
                    exc_info=True,
                )
        await self._db.delete(doc)
        await self._db.commit()

    async def get_markdown_preview(self, document_id: UUID) -> str:
        doc = await self.get_document(document_id)
        storage = get_handbook_storage()
        key = doc.derived_markdown_object_key or doc.object_key
        try:
            data = storage.get_object(key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Markdown not found in storage") from exc
        if doc.source_content_type == "application/pdf" and not doc.derived_markdown_object_key:
            raise HTTPException(
                status_code=409,
                detail="Run reindex/ingest first to generate derived Markdown from PDF",
            )
        return data.decode("utf-8")

    async def search_preview(
        self,
        *,
        query: str,
        top_k: int,
        min_score: float | None = None,
    ) -> list[dict]:
        settings = get_knowledge_settings()
        embedder = get_embedder(settings)
        vector = embedder.embed_query(query)
        threshold = settings.min_score if min_score is None else min_score
        hits = get_knowledge_store().retrieve(
            vector,
            top_k=top_k,
            min_score=threshold,
        )
        return [
            {
                "document_id": hit.document_id,
                "title": hit.title,
                "section_title": hit.section_title,
                "score": hit.score,
                "excerpt": hit.body[:400],
            }
            for hit in hits
        ]

    async def _unique_slug(self, org_id: str, base: str) -> str:
        candidate = base
        suffix = 2
        while True:
            existing = await self._db.execute(
                select(KbDocument.id).where(
                    KbDocument.org_id == org_id,
                    KbDocument.slug == candidate,
                )
            )
            if existing.scalar_one_or_none() is None:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    async def _run_ingest(
        self,
        doc: KbDocument,
        *,
        principal: AdminPrincipal,
        publish: bool,
    ) -> KbIngestJob:
        job = KbIngestJob(id=uuid4(), document_id=doc.id, status="running")
        job.started_at = datetime.now(UTC)
        self._db.add(job)
        await self._db.flush()

        storage = get_handbook_storage()
        try:
            source_bytes = storage.get_object(doc.object_key)
            filename = doc.object_key.rsplit("/", 1)[-1]
            result = ingest_document(
                document_id=doc.id,
                title=doc.title,
                source_bytes=source_bytes,
                content_type=doc.source_content_type,
                filename=filename,
                version=doc.version,
                category_tags=list(doc.category_tags or []),
                status="published" if publish else "draft",
                storage=storage,
                org_id=doc.org_id or "default",
                object_key=doc.object_key,
            )
            doc.checksum_sha256 = result.checksum_sha256
            doc.chunk_count = result.chunk_count
            doc.embedding_model = result.embedding_model
            doc.converter_name = result.converter_name
            doc.converter_version = result.converter_version
            doc.derived_markdown_object_key = result.derived_markdown_object_key
            doc.qdrant_collection = get_knowledge_settings().qdrant_collection
            doc.updated_by = _actor_label(principal)
            if publish:
                doc.status = "published"
                doc.published_at = datetime.now(UTC)
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
        except Exception as exc:
            logger.exception("KB ingest failed for %s", doc.id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            await self._db.flush()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingest failed: {exc}",
            ) from exc

        await self._db.flush()
        return job
