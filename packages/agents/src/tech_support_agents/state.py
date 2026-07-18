from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from tech_support_orchestration.models import OrchestrationResult, StructuredIntent, TicketCommand


class SupportGraphState(TypedDict, total=False):
    session_id: str
    user_id: str
    user_email: str | None
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str
    message_count: int
    structured_intent: StructuredIntent | None
    orchestration_result: OrchestrationResult | None
    approved_command: TicketCommand | None
    provider_response: dict[str, Any] | None
    assistant_reply: str | None
    system_statuses: list[str]
    ui_card: dict[str, Any] | None
    active_ticket_number: str | None
    pending_attachments: list[dict[str, Any]]
    error: str | None
    needs_clarification: bool
    # KB / RAG troubleshoot (Phase 2)
    kb_rag_enabled: bool
    troubleshoot: dict[str, Any]
    troubleshoot_deflection: dict[str, Any] | None
    is_support_issue: bool
    problem_summary: str | None
