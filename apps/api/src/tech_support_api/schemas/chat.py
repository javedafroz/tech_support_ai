from datetime import datetime
from uuid import UUID

from typing import Self

from pydantic import BaseModel, Field, model_validator

from tech_support_api.schemas.attachments import AttachmentRef


class SessionContextSchema(BaseModel):
    active_ticket_number: str | None = None
    last_message_at: str | None = None
    message_count: int = 0


class SessionCreate(BaseModel):
    org_id: str | None = None


class SessionResponse(BaseModel):
    id: UUID
    user_id: str
    org_id: str | None
    status: str
    active_ticket_number: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class SessionContextResponse(BaseModel):
    session_id: UUID
    context: SessionContextSchema | None


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=16000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def require_content_or_attachments(self) -> Self:
        if not self.content.strip() and not self.attachment_ids:
            raise ValueError("Message must include text or at least one attachment.")
        return self


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str | None
    card: dict | None
    attachments: list[AttachmentRef] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    system_statuses: list[str] = Field(
        default_factory=list,
        description="User-facing processing labels from mock graph (Sprint 4)",
    )
    detected_intent: str | None = None


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str] | None = None


class PublicConfigResponse(BaseModel):
    thought_streaming_enabled: bool
