"""Build LLM gateway instances from settings."""

from __future__ import annotations

from tech_support_agents.llm_gateway import LLMGateway
from tech_support_agents.llm_settings import LLMSettings, get_llm_settings
from tech_support_agents.providers.anthropic import build_anthropic_gateway
from tech_support_agents.providers.azure_openai import build_azure_openai_gateway
from tech_support_agents.providers.mock import MockConversationLLM
from tech_support_agents.providers.openai import build_openai_gateway

_BUILDERS = {
    "openai": build_openai_gateway,
    "azure_openai": build_azure_openai_gateway,
    "anthropic": build_anthropic_gateway,
}


def build_llm_gateway(settings: LLMSettings | None = None) -> LLMGateway:
    """Construct the configured conversation LLM gateway."""
    resolved = settings or get_llm_settings()
    provider = resolved.resolved_provider()
    if provider is None:
        return MockConversationLLM()

    error = resolved.configuration_error(provider)
    if error:
        raise RuntimeError(error)

    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return builder(resolved)


def get_conversation_llm(settings: LLMSettings | None = None) -> LLMGateway:
    """Return the active conversation LLM gateway (alias for build_llm_gateway)."""
    return build_llm_gateway(settings)
