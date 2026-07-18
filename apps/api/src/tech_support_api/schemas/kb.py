from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KbDocumentResponse(BaseModel):
    id: UUID
    org_id: str | None = None
    title: str
    slug: str
    status: str
    category_tags: list[str] = Field(default_factory=list)
    source_content_type: str
    object_key: str
    derived_markdown_object_key: str | None = None
    version: int
    chunk_count: int | None = None
    converter_name: str | None = None
    converter_version: str | None = None
    embedding_model: str | None = None
    published_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KbDocumentListResponse(BaseModel):
    items: list[KbDocumentResponse]
    total: int


class KbDocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    category_tags: list[str] | None = None
    status: str | None = None


class KbMeResponse(BaseModel):
    subject: str
    username: str | None = None
    email: str | None = None
    roles: list[str]
    can_edit: bool
    can_publish: bool


class KbSearchPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class KbSearchPreviewHit(BaseModel):
    document_id: UUID
    title: str
    section_title: str | None = None
    score: float
    excerpt: str


class KbSearchPreviewResponse(BaseModel):
    hits: list[KbSearchPreviewHit]
    note: str | None = None


class KbMarkdownPreviewResponse(BaseModel):
    document_id: UUID
    markdown: str


class KbIngestJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
