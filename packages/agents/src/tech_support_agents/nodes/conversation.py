from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import HumanMessage
from tech_support_orchestration.models import IntentName, StructuredIntent

from tech_support_agents.attachment_content import attachment_has_images
from tech_support_agents.llm import get_conversation_llm
from tech_support_agents.state import SupportGraphState

logger = logging.getLogger(__name__)


def _build_add_attachment_intent(
    *,
    session_id: UUID,
    user_id: str,
    ticket_number: str,
    attachments: list[dict],
    user_input: str,
) -> StructuredIntent:
    return StructuredIntent(
        intent=IntentName.ADD_ATTACHMENT,
        confidence=0.95,
        session_id=session_id,
        user_id=user_id,
        payload={
            "ticket_number": ticket_number,
            "attachments": attachments,
            "note": user_input.strip() or "Attachment added via Tech Support AI chat.",
        },
        timestamp=datetime.now(UTC),
    )


async def conversation_node(state: SupportGraphState) -> dict:
    user_input = state.get("user_input", "")
    session_id = UUID(state["session_id"])
    user_id = state["user_id"]
    user_email = state.get("user_email")
    messages = state.get("messages", [])
    prior_user_turns = sum(1 for m in messages if isinstance(m, HumanMessage))
    message_count = state.get("message_count", prior_user_turns)
    pending_attachments = list(state.get("pending_attachments") or [])
    active_ticket_number = state.get("active_ticket_number")

    updates: dict = {
        "messages": [
            HumanMessage(content=user_input),
        ],
        "system_statuses": ["Thinking…", "Checking your request…"],
    }
    if pending_attachments and attachment_has_images(pending_attachments):
        updates["system_statuses"].append("Reading attachment…")

    if pending_attachments and active_ticket_number:
        structured = _build_add_attachment_intent(
            session_id=session_id,
            user_id=user_id,
            ticket_number=active_ticket_number,
            attachments=pending_attachments,
            user_input=user_input,
        )
        updates["structured_intent"] = structured
        updates["needs_clarification"] = False
        return updates

    is_support_issue = False
    problem_summary: str | None = None
    try:
        gateway = get_conversation_llm()
        turn = await gateway.propose_intent(
            user_input,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
            message_count=message_count,
            history=messages,
            pending_attachments=pending_attachments,
        )
        structured, clarify = turn.structured_intent, turn.reply
        is_support_issue = turn.is_support_issue
        problem_summary = turn.problem_summary
    except Exception:
        logger.exception("Conversation LLM failed")
        structured, clarify = (
            None,
            "I'm having trouble processing your message right now. Please try again in a moment.",
        )

    if structured and pending_attachments:
        payload = dict(structured.payload)
        payload["attachments"] = pending_attachments
        structured = structured.model_copy(update={"payload": payload})

    updates["is_support_issue"] = is_support_issue
    updates["problem_summary"] = problem_summary

    if structured:
        updates["structured_intent"] = structured
        updates["needs_clarification"] = False
    else:
        updates["needs_clarification"] = True
        # While KB guiding owns the turn, do not set a clarify reply — the
        # troubleshoot node will present the next step or escalate to a ticket.
        guiding = (state.get("troubleshoot") or {}).get("status") == "guiding"
        if not guiding:
            updates["assistant_reply"] = clarify

    return updates
