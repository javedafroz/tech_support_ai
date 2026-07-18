from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ProviderCapabilities(BaseModel):
    supports_attachments: bool = False
    supports_escalation: bool = False
    supports_close: bool = False
    supports_status_search: bool = False


class ProviderTicket(BaseModel):
    provider: str
    external_id: str
    display_number: str
    state: str | None = None
    group_or_queue: str | None = None
    priority: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TicketOperationResult(BaseModel):
    success: bool
    provider: str
    operation: TicketCommandType | str
    ticket: ProviderTicket | None = None
    items: list[ProviderTicket] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
