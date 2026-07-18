"""OpenAI conversation provider."""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from tech_support_agents.llm_settings import LLMSettings
from tech_support_agents.providers.structured import (
    StructuredConversationLLM,
    build_structured_gateway,
)


def build_openai_gateway(settings: LLMSettings) -> StructuredConversationLLM:
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": settings.llm_temperature,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    llm = ChatOpenAI(**kwargs)
    return build_structured_gateway("openai", llm)
