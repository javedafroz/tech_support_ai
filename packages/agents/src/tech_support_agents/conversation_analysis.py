"""Shared conversation schema, prompts, and intent conversion for all LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from tech_support_orchestration.mapping import normalize_customer_email
from tech_support_orchestration.models import IntentName, StructuredIntent

from tech_support_agents.attachment_content import (
    build_attachment_prompt_context,
    build_user_message_content,
)

IntentLiteral = Literal[
    "CreateTicket",
    "CheckStatus",
    "UpdateTicket",
    "AddAttachment",
    "EscalateIssue",
    "CancelTicket",
]

SYSTEM_PROMPT = """You are a professional IT tech support assistant integrated with Ticket Management System.

Your job in each turn:
1. Reply naturally and helpfully to the user (`reply_to_user`).
2. Decide whether you have enough information to propose a structured intent (`ready_for_orchestration`).

Multi-turn rules (critical):
- Review the ENTIRE conversation history before deciding readiness — facts may be spread across turns.
- Synthesize `title` and `description` from ALL user messages in the session, not only the latest turn.
- Do NOT re-ask for information the user already provided in prior turns; ask at most one targeted
  question for a genuinely missing field.
- Minimum bar for CreateTicket across the full thread: problem/symptom plus when it started or
  current impact (error messages count as impact).
- When the user says they already provided details or expresses frustration, re-read the full
  history; if the minimum bar is met, set ready_for_orchestration=true.
- Prefer the primary incident (e.g. blue screen, hardware failure) over incidental context
  (e.g. which app they had open).

Rules:
- Never invent or guess ticket numbers. Ticket IDs only come from Zammad after creation.
- Use CreateTicket when the user describes a concrete support issue with enough detail
  (what is wrong, impact, and ideally when it started or any error messages).
- Use CheckStatus when the user asks about an existing ticket and provides a ticket number.
- Set `confidence` between 0 and 1 when ready_for_orchestration is true.
- For CreateTicket, set title, description, customer_email (plain address only — e.g.
  user@company.com, never Zammad search syntax like email:user@company.com; prefer session email),
  suggested_category (hardware, software, network, security, email, access_management,
  infrastructure), and suggested_priority (low, normal, or high).
- For CheckStatus, set ticket_number when the user provided one.
- When images are attached in this turn, inspect them for error codes, stop codes, dialog
  text, and symptoms. Include what you read in title/description — do not ask the user to
  re-type information that is clearly visible in an attached screenshot.
- If information is missing, set ready_for_orchestration to false and ask clarifying questions
  in reply_to_user.
- Supported intents only: CreateTicket, CheckStatus, UpdateTicket, AddAttachment,
  EscalateIssue, CancelTicket.

Troubleshooting signal (important):
- Set `is_support_issue` to true the moment the user reports a NEW technical problem they want
  help with (a CreateTicket-type issue) — even on the very first message and even while
  `ready_for_orchestration` is still false because you are still gathering ticket details.
- Set `is_support_issue` to false for greetings, status checks (CheckStatus), attachment-only
  turns, and small talk.
- Whenever `is_support_issue` is true, always fill `problem_summary` with a concise one or two
  sentence description of the problem synthesized from the ENTIRE conversation. This summary is
  used to search the self-help knowledge base, so make it specific (mention the product, symptom,
  and any error text).
"""


class ConversationAnalysis(BaseModel):
    """Structured output from the conversation LLM (strict schema for structured output)."""

    model_config = ConfigDict(extra="forbid")

    reply_to_user: str = Field(description="Natural language message shown to the user")
    ready_for_orchestration: bool = Field(
        description="True when a structured intent can be sent to policy orchestration"
    )
    is_support_issue: bool = Field(
        default=False,
        description="True when the user is reporting a new technical problem (CreateTicket-type), "
        "even before all ticket fields are known",
    )
    problem_summary: str | None = Field(
        default=None,
        description="Concise problem description for knowledge-base search (set when is_support_issue)",
    )
    intent: IntentLiteral | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    title: str | None = None
    description: str | None = Field(
        default=None,
        description="Full issue narrative synthesized from all user messages in this session",
    )
    customer_email: str | None = None
    suggested_category: str | None = None
    suggested_priority: str | None = None
    ticket_number: str | None = None
    search_hint: str | None = None


def build_prompt_messages(
    user_text: str,
    *,
    session_id: UUID,
    user_id: str,
    user_email: str | None,
    message_count: int,
    history: list[BaseMessage],
    pending_attachments: list[dict] | None = None,
    llm_provider: str = "openai",
) -> list[BaseMessage]:
    context = (
        f"Session id: {session_id}\n"
        f"User id: {user_id}\n"
        f"User email: {user_email or '(not provided)'}\n"
        f"Prior user turns in session: {message_count}\n"
    )

    vision_blocks, attachment_summary = build_attachment_prompt_context(
        pending_attachments or [],
        llm_provider=llm_provider,
    )
    if attachment_summary:
        context += f"\nAttachments in this turn:\n{attachment_summary}\n"

    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT + "\n\n" + context)]

    for message in history[-12:]:
        if isinstance(message, HumanMessage):
            messages.append(HumanMessage(content=str(message.content)))
        elif isinstance(message, AIMessage):
            messages.append(AIMessage(content=str(message.content)))

    messages.append(
        HumanMessage(
            content=build_user_message_content(
                user_text,
                vision_blocks=vision_blocks,
                llm_provider=llm_provider,
            ),
        )
    )
    return messages


def payload_from_analysis(
    analysis: ConversationAnalysis,
    *,
    user_id: str,
    user_email: str | None,
) -> dict[str, Any]:
    if analysis.intent == "CreateTicket":
        email = normalize_customer_email((user_email or analysis.customer_email or "").strip())
        if not email and "@" in user_id:
            email = normalize_customer_email(user_id)
        title = (analysis.title or "").strip() or (analysis.description or "Support request")[:80]
        description = (analysis.description or "").strip() or title
        payload: dict[str, Any] = {
            "title": title,
            "description": description,
        }
        if email:
            payload["customer_email"] = email
        if analysis.suggested_category:
            payload["suggested_category"] = analysis.suggested_category
        if analysis.suggested_priority:
            payload["suggested_priority"] = analysis.suggested_priority
        return payload

    if analysis.intent == "CheckStatus":
        payload = {}
        if analysis.ticket_number:
            payload["ticket_number"] = analysis.ticket_number
        if analysis.search_hint:
            payload["search_hint"] = analysis.search_hint
        return payload

    payload = {}
    for key in (
        "title",
        "description",
        "customer_email",
        "suggested_category",
        "suggested_priority",
        "ticket_number",
        "search_hint",
    ):
        value = getattr(analysis, key, None)
        if value:
            payload[key] = value
    return payload


@dataclass
class ConversationTurn:
    """Result of one conversation LLM turn."""

    structured_intent: StructuredIntent | None
    reply: str | None
    is_support_issue: bool = False
    problem_summary: str | None = None


def analysis_to_result(
    analysis: ConversationAnalysis,
    *,
    session_id: UUID,
    user_id: str,
    user_email: str | None,
) -> ConversationTurn:
    is_support_issue = bool(analysis.is_support_issue)
    problem_summary = (analysis.problem_summary or "").strip() or None

    if not analysis.ready_for_orchestration or not analysis.intent:
        return ConversationTurn(
            structured_intent=None,
            reply=analysis.reply_to_user,
            is_support_issue=is_support_issue,
            problem_summary=problem_summary,
        )

    try:
        intent_name = IntentName(analysis.intent)
    except ValueError:
        return ConversationTurn(
            structured_intent=None,
            reply=analysis.reply_to_user,
            is_support_issue=is_support_issue,
            problem_summary=problem_summary,
        )

    structured = StructuredIntent(
        intent=intent_name,
        confidence=float(analysis.confidence or 0.85),
        session_id=session_id,
        user_id=user_id,
        payload=payload_from_analysis(analysis, user_id=user_id, user_email=user_email),
        timestamp=datetime.now(UTC),
    )
    return ConversationTurn(
        structured_intent=structured,
        reply=None,
        is_support_issue=is_support_issue,
        problem_summary=problem_summary,
    )
