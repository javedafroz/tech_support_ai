from __future__ import annotations

import logging
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from tech_support_agents.llm import get_conversation_llm
from tech_support_agents.state import SupportGraphState

logger = logging.getLogger(__name__)


async def conversation_node(state: SupportGraphState) -> dict:
    user_input = state.get("user_input", "")
    session_id = UUID(state["session_id"])
    user_id = state["user_id"]
    user_email = state.get("user_email")
    messages = state.get("messages", [])
    prior_user_turns = sum(1 for m in messages if isinstance(m, HumanMessage))
    message_count = state.get("message_count", prior_user_turns)

    updates: dict = {
        "messages": [
            HumanMessage(content=user_input),
        ],
        "system_statuses": ["Thinking…", "Checking your request…"],
    }

    try:
        llm = get_conversation_llm()
        if hasattr(llm, "apropose_intent"):
            structured, clarify = await llm.apropose_intent(
                user_input,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                message_count=message_count,
                history=messages,
            )
        elif hasattr(llm, "propose_intent"):
            structured, clarify = llm.propose_intent(
                user_input,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                message_count=message_count,
            )
        else:
            structured, clarify = None, "LLM provider not configured for structured output."
    except Exception:
        logger.exception("Conversation LLM failed")
        structured, clarify = (
            None,
            "I'm having trouble processing your message right now. Please try again in a moment.",
        )

    if structured:
        updates["structured_intent"] = structured
        updates["needs_clarification"] = False
    else:
        updates["needs_clarification"] = True
        updates["assistant_reply"] = clarify
        updates["messages"].append(AIMessage(content=clarify or ""))

    return updates
