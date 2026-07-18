from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentRef(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    size_bytes: int


class AttachmentUploadResponse(BaseModel):
    id: UUID
    session_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentListResponse(BaseModel):
    attachments: list[AttachmentUploadResponse]
