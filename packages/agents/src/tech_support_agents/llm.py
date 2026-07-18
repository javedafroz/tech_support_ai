"""LLM package public API — settings, gateway factory, and backward-compatible exports."""

from tech_support_agents.llm_factory import build_llm_gateway, get_conversation_llm
from tech_support_agents.llm_gateway import LLMGateway
from tech_support_agents.llm_settings import (
    LLMSettings,
    configure_llm,
    get_llm_settings,
    merge_llm_settings,
)
from tech_support_agents.providers.mock import MockConversationLLM

__all__ = [
    "LLMGateway",
    "LLMSettings",
    "MockConversationLLM",
    "build_llm_gateway",
    "configure_llm",
    "get_conversation_llm",
    "get_llm_settings",
    "merge_llm_settings",
]
