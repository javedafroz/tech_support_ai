"""Shared structured-output conversation + RAG provider built on LangChain chat models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from tech_support_agents.conversation_analysis import (
    ConversationAnalysis,
    ConversationTurn,
    analysis_to_result,
    build_prompt_messages,
)
from tech_support_agents.llm_gateway import TroubleshootOutcomeLabel
from tech_support_agents.rag_guidance import (
    TroubleshootGuidance,
    TroubleshootOutcomeAnalysis,
    build_outcome_prompt_messages,
    build_rag_prompt_messages,
)


class StructuredConversationLLM:
    """Provider implementation that uses LangChain structured output."""

    def __init__(
        self,
        *,
        provider_name: str,
        chain: Runnable,
        rag_chain: Runnable | None = None,
        outcome_chain: Runnable | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._chain = chain
        self._rag_chain = rag_chain
        self._outcome_chain = outcome_chain

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def propose_intent(
        self,
        user_text: str,
        *,
        session_id: UUID,
        user_id: str,
        user_email: str | None,
        message_count: int,
        history: list[BaseMessage] | None = None,
        pending_attachments: list[dict] | None = None,
    ) -> ConversationTurn:
        analysis: ConversationAnalysis = await self._chain.ainvoke(
            build_prompt_messages(
                user_text,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                message_count=message_count,
                history=history or [],
                pending_attachments=pending_attachments,
                llm_provider=self._provider_name,
            )
        )
        return analysis_to_result(
            analysis,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
        )

    async def generate_troubleshoot_guidance(
        self,
        problem: str,
        contexts: list[dict[str, str]],
        *,
        history: list[BaseMessage] | None = None,
        max_steps: int = 5,
    ) -> TroubleshootGuidance:
        del history  # reserved for future multi-turn grounding
        if self._rag_chain is None:
            raise RuntimeError(f"{self._provider_name} gateway has no RAG chain configured")
        result = await self._rag_chain.ainvoke(
            build_rag_prompt_messages(problem=problem, contexts=contexts, max_steps=max_steps)
        )
        if isinstance(result, TroubleshootGuidance):
            return result
        return TroubleshootGuidance.model_validate(result)

    async def classify_troubleshoot_outcome(
        self,
        user_text: str,
        *,
        history: list[BaseMessage] | None = None,
    ) -> TroubleshootOutcomeLabel:
        del history
        if self._outcome_chain is None:
            return "unclear"
        result = await self._outcome_chain.ainvoke(
            build_outcome_prompt_messages(user_text=user_text)
        )
        if isinstance(result, TroubleshootOutcomeAnalysis):
            return result.outcome
        return TroubleshootOutcomeAnalysis.model_validate(result).outcome


def build_structured_chain(llm: Any) -> Runnable:
    return llm.with_structured_output(ConversationAnalysis)


def build_rag_chain(llm: Any) -> Runnable:
    return llm.with_structured_output(TroubleshootGuidance)


def build_outcome_chain(llm: Any) -> Runnable:
    return llm.with_structured_output(TroubleshootOutcomeAnalysis)


def build_structured_gateway(provider_name: str, llm: Any) -> StructuredConversationLLM:
    """Build a gateway with conversation, RAG, and outcome chains from one model."""
    return StructuredConversationLLM(
        provider_name=provider_name,
        chain=build_structured_chain(llm),
        rag_chain=build_rag_chain(llm),
        outcome_chain=build_outcome_chain(llm),
    )
