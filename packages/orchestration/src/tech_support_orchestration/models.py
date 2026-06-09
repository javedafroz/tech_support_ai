from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IntentName(StrEnum):
    CREATE_TICKET = "CreateTicket"
    CHECK_STATUS = "CheckStatus"
    UPDATE_TICKET = "UpdateTicket"
    ADD_ATTACHMENT = "AddAttachment"
    ESCALATE_ISSUE = "EscalateIssue"
    CANCEL_TICKET = "CancelTicket"


class StructuredIntent(BaseModel):
    intent: IntentName | str
    confidence: float = Field(ge=0, le=1)
    session_id: UUID
    user_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class UserContext(BaseModel):
    user_id: str
    email: str | None = None


class PolicyOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ValidationResult(BaseModel):
    passed: bool
    reason_code: str | None = None
    message: str | None = None
    rule_id: str | None = None


class TicketCommandType(StrEnum):
    CREATE_TICKET = "CreateTicket"
    GET_TICKET = "GetTicket"
    SEARCH_TICKETS = "SearchTickets"
    UPDATE_TICKET = "UpdateTicket"
    ADD_ARTICLE = "AddArticle"
    ADD_ATTACHMENT = "AddAttachment"
    ESCALATE_TICKET = "EscalateTicket"
    CLOSE_TICKET = "CloseTicket"


class TicketCommand(BaseModel):
    type: TicketCommandType | str
    session_id: UUID
    user_id: str
    idempotency_key: UUID = Field(default_factory=uuid4)
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationResult(BaseModel):
    outcome: PolicyOutcome
    reason_code: str | None = None
    rule_id: str | None = None
    approved_command: TicketCommand | None = None
    validation: ValidationResult | None = None
