from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from tech_support_agents.llm import LLMSettings, configure_llm, get_conversation_llm
from tech_support_agents.openai_llm import (
    ConversationAnalysis,
    OpenAIConversationLLM,
    _build_prompt_messages,
)
from tech_support_orchestration.models import IntentName


def test_get_openai_llm_requires_api_key():
    configure_llm(LLMSettings(graph_llm_mode="openai", llm_provider="openai", openai_api_key=None))
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
    turn = await llm.propose_intent(
        "VPN auth fails since morning",
        session_id=session_id,
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=2,
    )

    assert turn.reply is None
    assert turn.structured_intent is not None
    assert turn.structured_intent.intent == IntentName.CREATE_TICKET
    assert turn.structured_intent.payload["customer_email"] == "user@company.com"
    assert turn.structured_intent.confidence == 0.92


@pytest.mark.asyncio
async def test_openai_propose_intent_clarification():
    llm = OpenAIConversationLLM(api_key="test-key")
    llm._chain = MagicMock()
    llm._chain.ainvoke = AsyncMock(
        return_value=ConversationAnalysis(
            reply_to_user="What error do you see?",
            ready_for_orchestration=False,
            is_support_issue=True,
            problem_summary="VPN is broken",
        )
    )

    turn = await llm.propose_intent(
        "VPN broken",
        session_id=uuid4(),
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=0,
    )

    assert turn.structured_intent is None
    assert turn.reply is not None
    assert "error" in turn.reply.lower()
    assert turn.is_support_issue is True
    assert turn.problem_summary == "VPN is broken"


def test_build_prompt_messages_includes_conversation_history():
    session_id = uuid4()
    messages = _build_prompt_messages(
        "Started this morning",
        session_id=session_id,
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=2,
        history=[
            HumanMessage(content="Blue screen on my laptop"),
            AIMessage(content="When did it start?"),
        ],
    )

    contents = [str(message.content) for message in messages]
    assert any("Blue screen on my laptop" in content for content in contents)
    assert any("When did it start?" in content for content in contents)
    assert contents[-1] == "Started this morning"
