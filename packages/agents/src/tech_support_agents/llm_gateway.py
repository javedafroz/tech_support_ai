"""LLM gateway protocol — provider-agnostic conversation and RAG interface."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from langchain_core.messages import BaseMessage

from tech_support_agents.conversation_analysis import ConversationTurn
from tech_support_agents.rag_guidance import TroubleshootGuidance

TroubleshootOutcomeLabel = Literal["resolved", "failed", "escalate", "unclear"]


class LLMGateway(Protocol):
    """Abstraction for conversation LLM providers (OpenAI, Azure OpenAI, Anthropic, mock)."""

    @property
    def provider_name(self) -> str:
        """Provider identifier, e.g. openai, azure_openai, anthropic, mock."""
        ...

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
        ...

    async def generate_troubleshoot_guidance(
        self,
        problem: str,
        contexts: list[dict[str, str]],
        *,
        history: list[BaseMessage] | None = None,
        max_steps: int = 5,
    ) -> TroubleshootGuidance:
        """Synthesize adaptive grounded troubleshooting guidance from retrieved sources."""
        ...

    async def classify_troubleshoot_outcome(
        self,
        user_text: str,
        *,
        history: list[BaseMessage] | None = None,
    ) -> TroubleshootOutcomeLabel:
        """Classify an ambiguous user reply during troubleshooting."""
        ...
