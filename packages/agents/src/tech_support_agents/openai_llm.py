"""Backward-compatible OpenAI LLM module — prefer llm_factory.build_llm_gateway()."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from tech_support_agents.conversation_analysis import (
    ConversationAnalysis,
    ConversationTurn,
    analysis_to_result,
    build_prompt_messages,
)
from tech_support_agents.providers.structured import (
    StructuredConversationLLM,
    build_structured_gateway,
)

# Re-export for existing tests and imports.
_build_prompt_messages = build_prompt_messages
_analysis_to_result = analysis_to_result
__all__ = [
    "ConversationAnalysis",
    "ConversationTurn",
    "OpenAIConversationLLM",
    "_analysis_to_result",
    "_build_prompt_messages",
]


class OpenAIConversationLLM(StructuredConversationLLM):
    """OpenAI-backed conversation LLM (legacy class name)."""

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
        gateway = build_structured_gateway("openai", ChatOpenAI(**kwargs))
        super().__init__(
            provider_name=gateway.provider_name,
            chain=gateway._chain,
            rag_chain=gateway._rag_chain,
            outcome_chain=gateway._outcome_chain,
        )

    async def apropose_intent(
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
        return await self.propose_intent(
            user_text,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
            message_count=message_count,
            history=history,
            pending_attachments=pending_attachments,
        )
