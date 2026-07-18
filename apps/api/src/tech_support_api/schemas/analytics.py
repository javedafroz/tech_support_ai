from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HandbookBreakdownItem(BaseModel):
    document_id: UUID | None = None
    title: str
    resolved: int = 0
    escalated: int = 0


class AnalyticsSummaryResponse(BaseModel):
    total_conversations: int
    total_messages: int
    tickets_created: int
    deflections_resolved: int
    deflections_escalated: int
    deflection_rate: float = Field(
        description="resolved / (resolved + escalated); 0 when no deflection events",
    )
    by_handbook: list[HandbookBreakdownItem] = Field(default_factory=list)


class SessionAnalyticsItem(BaseModel):
    id: UUID
    user_id: str
    org_id: str | None = None
    status: str
    active_ticket_number: str | None = None
    message_count: int
    deflection_outcome: str | None = None
    deflection_steps_count: int | None = None
    handbook_document_id: UUID | None = None
    handbook_title: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionAnalyticsListResponse(BaseModel):
    items: list[SessionAnalyticsItem]
    total: int


class TranscriptMessage(BaseModel):
    id: UUID
    role: str
    content: str | None = None
    card: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionTranscriptResponse(BaseModel):
    session_id: UUID
    messages: list[TranscriptMessage]


class TrendDayItem(BaseModel):
    date: str = Field(description="ISO date YYYY-MM-DD")
    conversations: int = 0
    resolved: int = 0
    escalated: int = 0


class AnalyticsTrendsResponse(BaseModel):
    days: int
    items: list[TrendDayItem] = Field(default_factory=list)
