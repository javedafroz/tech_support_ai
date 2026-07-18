"""Admin KB API — Keycloak-protected handbook management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_api.db.models import KbDocument, KbIngestJob
from tech_support_api.db.session import get_db
from tech_support_api.dependencies.keycloak_auth import (
    AdminPrincipal,
    require_kb_admin,
    require_kb_editor,
)
from tech_support_api.schemas.kb import (
    KbDocumentListResponse,
    KbDocumentResponse,
    KbDocumentUpdateRequest,
    KbIngestJobResponse,
    KbMarkdownPreviewResponse,
    KbMeResponse,
    KbSearchPreviewHit,
    KbSearchPreviewRequest,
    KbSearchPreviewResponse,
)
from tech_support_api.services.kb_service import KbService

router = APIRouter(prefix="/admin/kb", tags=["admin-kb"])


def _doc_response(doc: KbDocument) -> KbDocumentResponse:
    return KbDocumentResponse(
        id=doc.id,
        org_id=doc.org_id,
        title=doc.title,
        slug=doc.slug,
        status=doc.status,
        category_tags=list(doc.category_tags or []),
        source_content_type=doc.source_content_type,
        object_key=doc.object_key,
        derived_markdown_object_key=doc.derived_markdown_object_key,
        version=doc.version,
        chunk_count=doc.chunk_count,
        converter_name=doc.converter_name,
        converter_version=doc.converter_version,
        embedding_model=doc.embedding_model,
        published_at=doc.published_at,
        created_by=doc.created_by,
        updated_by=doc.updated_by,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/me", response_model=KbMeResponse)
async def kb_me(
    principal: AdminPrincipal = Depends(require_kb_editor),
) -> KbMeResponse:
    return KbMeResponse(
        subject=principal.subject,
        username=principal.username,
        email=principal.email,
        roles=sorted(principal.roles),
        can_edit=principal.can_edit,
        can_publish=principal.can_publish,
    )


@router.get("/documents", response_model=KbDocumentListResponse)
async def list_documents(
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> KbDocumentListResponse:
    del principal
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    total = int((await db.execute(select(func.count()).select_from(KbDocument))).scalar_one())
    result = await db.execute(
        select(KbDocument).order_by(KbDocument.updated_at.desc()).offset(offset).limit(limit)
    )
    docs = list(result.scalars().all())
    return KbDocumentListResponse(items=[_doc_response(doc) for doc in docs], total=total)


@router.post(
    "/documents",
    response_model=KbDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    org_id: str | None = Form(default=None),
    category_tags: str | None = Form(
        default=None,
        description="Comma-separated tags, e.g. network,vpn",
    ),
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbDocumentResponse:
    tags = [t.strip() for t in (category_tags or "").split(",") if t.strip()]
    service = KbService(db)
    doc = await service.create_from_upload(
        principal=principal,
        file=file,
        title=title,
        org_id=org_id,
        category_tags=tags,
        auto_ingest=True,
    )
    return _doc_response(doc)


@router.get("/documents/{document_id}", response_model=KbDocumentResponse)
async def get_document(
    document_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbDocumentResponse:
    del principal
    doc = await KbService(db).get_document(document_id)
    return _doc_response(doc)


@router.patch("/documents/{document_id}", response_model=KbDocumentResponse)
async def update_document(
    document_id: UUID,
    body: KbDocumentUpdateRequest,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbDocumentResponse:
    doc = await KbService(db).update_document(
        document_id,
        principal=principal,
        title=body.title,
        category_tags=body.category_tags,
        status=body.status,
    )
    return _doc_response(doc)


@router.post("/documents/{document_id}/publish", response_model=KbDocumentResponse)
async def publish_document(
    document_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_admin),
    db: AsyncSession = Depends(get_db),
) -> KbDocumentResponse:
    doc = await KbService(db).publish(document_id, principal=principal)
    return _doc_response(doc)


@router.post("/documents/{document_id}/reindex", response_model=KbIngestJobResponse)
async def reindex_document(
    document_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbIngestJobResponse:
    job = await KbService(db).reindex(document_id, principal=principal)
    return KbIngestJobResponse.model_validate(job)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await KbService(db).delete_document(document_id, principal=principal)


@router.get(
    "/documents/{document_id}/markdown",
    response_model=KbMarkdownPreviewResponse,
)
async def preview_markdown(
    document_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbMarkdownPreviewResponse:
    del principal
    markdown = await KbService(db).get_markdown_preview(document_id)
    return KbMarkdownPreviewResponse(document_id=document_id, markdown=markdown)


@router.get("/jobs/{job_id}", response_model=KbIngestJobResponse)
async def get_job(
    job_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbIngestJobResponse:
    del principal
    job = await db.get(KbIngestJob, job_id)
    if job is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job not found")
    return KbIngestJobResponse.model_validate(job)


@router.post("/search/preview", response_model=KbSearchPreviewResponse)
async def search_preview(
    body: KbSearchPreviewRequest,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> KbSearchPreviewResponse:
    del principal
    hits = await KbService(db).search_preview(query=body.query, top_k=body.top_k)
    return KbSearchPreviewResponse(
        hits=[KbSearchPreviewHit(**hit) for hit in hits],
        note=None if hits else "No published chunks matched. Publish a handbook and try again.",
    )
