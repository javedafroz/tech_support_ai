"""Azure OpenAI conversation provider."""

from __future__ import annotations

from langchain_openai import AzureChatOpenAI

from tech_support_agents.llm_settings import LLMSettings
from tech_support_agents.providers.structured import (
    StructuredConversationLLM,
    build_structured_gateway,
)


def build_azure_openai_gateway(settings: LLMSettings) -> StructuredConversationLLM:
    llm = AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        api_key=settings.azure_openai_api_key,
        temperature=settings.llm_temperature,
    )
    return build_structured_gateway("azure_openai", llm)
