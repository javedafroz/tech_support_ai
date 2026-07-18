"""Provider-level classic RAG guidance tests (mock + structured prompt wiring)."""

from __future__ import annotations

import pytest

from tech_support_agents.conversation_analysis import ConversationAnalysis
from tech_support_agents.llm import LLMSettings, configure_llm, get_conversation_llm
from tech_support_agents.providers.mock import MockConversationLLM
from tech_support_agents.providers.structured import (
    StructuredConversationLLM,
    build_rag_chain,
    build_structured_gateway,
)
from tech_support_agents.rag_guidance import (
    RAG_SYSTEM_PROMPT,
    TroubleshootGuidance,
    TroubleshootOutcomeAnalysis,
    build_rag_prompt_messages,
)


@pytest.mark.asyncio
async def test_mock_generates_grounded_adaptive_steps():
    configure_llm(LLMSettings(graph_llm_mode="mock"))
    gateway = get_conversation_llm()
    assert isinstance(gateway, MockConversationLLM)
    guidance = await gateway.generate_troubleshoot_guidance(
        "Printer offline",
        [
            {"source_id": "src1", "body": "Check cables and Wi-Fi.", "section_title": "Print"},
            {"source_id": "src2", "body": "Restart the print spooler.", "section_title": "Spooler"},
        ],
        max_steps=5,
    )
    assert guidance.supported is True
    assert 1 <= len(guidance.steps) <= 2
    for step in guidance.steps:
        assert step.source_ids
        assert all(sid.startswith("src") for sid in step.source_ids)


@pytest.mark.asyncio
async def test_mock_unsupported_problem():
    gateway = MockConversationLLM()
    guidance = await gateway.generate_troubleshoot_guidance(
        "unsupported mystery issue",
        [{"source_id": "src1", "body": "VPN tip"}],
        max_steps=3,
    )
    assert guidance.supported is False
    assert guidance.steps == []


@pytest.mark.asyncio
async def test_mock_outcome_classifier():
    gateway = MockConversationLLM()
    assert await gateway.classify_troubleshoot_outcome("still broken") == "failed"
    assert await gateway.classify_troubleshoot_outcome("that fixed it") == "resolved"
    assert await gateway.classify_troubleshoot_outcome("open a ticket") == "escalate"
    assert await gateway.classify_troubleshoot_outcome("what?") == "unclear"


def test_rag_prompt_includes_sources_and_grounding_rules():
    assert "SOURCE" in RAG_SYSTEM_PROMPT
    assert "general knowledge" in RAG_SYSTEM_PROMPT.lower() or "ONLY" in RAG_SYSTEM_PROMPT
    messages = build_rag_prompt_messages(
        problem="cannot print",
        contexts=[{"source_id": "src1", "section_title": "Print", "body": "Check cables"}],
        max_steps=3,
    )
    joined = "\n".join(str(m.content) for m in messages)
    assert "src1" in joined
    assert "Check cables" in joined
    assert "cannot print" in joined
    assert "Max steps: 3" in joined


def test_structured_gateway_wires_rag_and_outcome_chains():
    class _FakeLLM:
        def with_structured_output(self, schema):
            return ("chain", schema)

    gateway = build_structured_gateway("openai", _FakeLLM())
    assert isinstance(gateway, StructuredConversationLLM)
    assert gateway._chain == ("chain", ConversationAnalysis)
    assert gateway._rag_chain == ("chain", TroubleshootGuidance)
    assert gateway._outcome_chain == ("chain", TroubleshootOutcomeAnalysis)


def test_build_rag_chain_uses_guidance_schema():
    class _FakeLLM:
        def with_structured_output(self, schema):
            return schema

    assert build_rag_chain(_FakeLLM()) is TroubleshootGuidance
