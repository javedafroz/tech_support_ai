"""Anthropic Claude conversation provider."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from tech_support_agents.llm_settings import LLMSettings
from tech_support_agents.providers.structured import (
    StructuredConversationLLM,
    build_structured_gateway,
)


def build_anthropic_gateway(settings: LLMSettings) -> StructuredConversationLLM:
    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=settings.llm_temperature,
    )
    return build_structured_gateway("anthropic", llm)
