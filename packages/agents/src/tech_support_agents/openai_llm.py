"""OpenAI-backed conversation LLM with structured intent extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from tech_support_orchestration.mapping import normalize_customer_email
from tech_support_orchestration.models import IntentName, StructuredIntent

IntentLiteral = Literal[
    "CreateTicket",
    "CheckStatus",
    "UpdateTicket",
    "AddAttachment",
    "EscalateIssue",
    "CancelTicket",
]

_SYSTEM_PROMPT = """You are a professional IT tech support assistant integrated with Zammad.

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
- If information is missing, set ready_for_orchestration to false and ask clarifying questions
  in reply_to_user.
- Supported intents only: CreateTicket, CheckStatus, UpdateTicket, AddAttachment,
  EscalateIssue, CancelTicket.
"""


class ConversationAnalysis(BaseModel):
    """Structured output from the conversation LLM (strict schema for OpenAI)."""

    model_config = ConfigDict(extra="forbid")

    reply_to_user: str = Field(description="Natural language message shown to the user")
    ready_for_orchestration: bool = Field(
        description="True when a structured intent can be sent to policy orchestration"
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


class OpenAIConversationLLM:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatOpenAI(**kwargs)
        self._chain = llm.with_structured_output(ConversationAnalysis)

    async def apropose_intent(
        self,
        user_text: str,
        *,
        session_id: UUID,
        user_id: str,
        user_email: str | None,
        message_count: int,
        history: list[BaseMessage] | None = None,
    ) -> tuple[StructuredIntent | None, str | None]:
        analysis = await self._chain.ainvoke(
            _build_prompt_messages(
                user_text,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                message_count=message_count,
                history=history or [],
            )
        )
        return _analysis_to_result(
            analysis,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
        )


def _build_prompt_messages(
    user_text: str,
    *,
    session_id: UUID,
    user_id: str,
    user_email: str | None,
    message_count: int,
    history: list[BaseMessage],
) -> list[BaseMessage]:
    context = (
        f"Session id: {session_id}\n"
        f"User id: {user_id}\n"
        f"User email: {user_email or '(not provided)'}\n"
        f"Prior user turns in session: {message_count}\n"
    )
    messages: list[BaseMessage] = [SystemMessage(content=_SYSTEM_PROMPT + "\n\n" + context)]

    for message in history[-12:]:
        if isinstance(message, HumanMessage):
            messages.append(HumanMessage(content=str(message.content)))
        elif isinstance(message, AIMessage):
            messages.append(AIMessage(content=str(message.content)))

    messages.append(HumanMessage(content=user_text))
    return messages


def _payload_from_analysis(
    analysis: ConversationAnalysis,
    *,
    user_id: str,
    user_email: str | None,
) -> dict[str, Any]:
    if analysis.intent == "CreateTicket":
        email = normalize_customer_email(
            (user_email or analysis.customer_email or "").strip()
        )
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


def _analysis_to_result(
    analysis: ConversationAnalysis,
    *,
    session_id: UUID,
    user_id: str,
    user_email: str | None,
) -> tuple[StructuredIntent | None, str | None]:
    if not analysis.ready_for_orchestration or not analysis.intent:
        return None, analysis.reply_to_user

    try:
        intent_name = IntentName(analysis.intent)
    except ValueError:
        return None, analysis.reply_to_user

    structured = StructuredIntent(
        intent=intent_name,
        confidence=float(analysis.confidence or 0.85),
        session_id=session_id,
        user_id=user_id,
        payload=_payload_from_analysis(analysis, user_id=user_id, user_email=user_email),
        timestamp=datetime.now(UTC),
    )
    return structured, None
