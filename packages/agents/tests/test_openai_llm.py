from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from tech_support_agents.llm import LLMSettings, configure_llm, get_conversation_llm
from tech_support_agents.openai_llm import ConversationAnalysis, OpenAIConversationLLM
from tech_support_orchestration.models import IntentName


def test_get_openai_llm_requires_api_key():
    configure_llm(LLMSettings(graph_llm_mode="openai", openai_api_key=None))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_conversation_llm()


@pytest.mark.asyncio
async def test_openai_propose_intent_create_ticket():
    llm = OpenAIConversationLLM(api_key="test-key", model="gpt-4o-mini")
    llm._chain = MagicMock()
    llm._chain.ainvoke = AsyncMock(
        return_value=ConversationAnalysis(
            reply_to_user="I'll create a ticket for your VPN issue.",
            ready_for_orchestration=True,
            intent="CreateTicket",
            confidence=0.92,
            title="VPN authentication failure",
            description="VPN auth fails since morning with 403 errors.",
            suggested_category="network",
            suggested_priority="high",
        )
    )

    session_id = uuid4()
    structured, clarify = await llm.apropose_intent(
        "VPN auth fails since morning",
        session_id=session_id,
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=2,
    )

    assert clarify is None
    assert structured is not None
    assert structured.intent == IntentName.CREATE_TICKET
    assert structured.payload["customer_email"] == "user@company.com"
    assert structured.confidence == 0.92


@pytest.mark.asyncio
async def test_openai_propose_intent_clarification():
    llm = OpenAIConversationLLM(api_key="test-key")
    llm._chain = MagicMock()
    llm._chain.ainvoke = AsyncMock(
        return_value=ConversationAnalysis(
            reply_to_user="What error do you see?",
            ready_for_orchestration=False,
        )
    )

    structured, clarify = await llm.apropose_intent(
        "VPN broken",
        session_id=uuid4(),
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=0,
    )

    assert structured is None
    assert "error" in clarify.lower()
