import pytest

from tech_support_agents.llm import LLMSettings, configure_llm, get_conversation_llm
from tech_support_agents.llm_factory import build_llm_gateway
from tech_support_agents.providers.mock import MockConversationLLM
from tech_support_agents.providers.structured import StructuredConversationLLM


def test_build_mock_gateway():
    configure_llm(LLMSettings(graph_llm_mode="mock"))
    gateway = build_llm_gateway()
    assert isinstance(gateway, MockConversationLLM)
    assert gateway.provider_name == "mock"


def test_build_openai_gateway_requires_api_key():
    configure_llm(LLMSettings(graph_llm_mode="openai", llm_provider="openai", openai_api_key=None))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_llm_gateway()


def test_build_openai_gateway_success():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="openai",
            openai_api_key="test-key",
        )
    )
    gateway = build_llm_gateway()
    assert isinstance(gateway, StructuredConversationLLM)
    assert gateway.provider_name == "openai"


def test_build_azure_openai_gateway_requires_credentials():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="azure_openai",
            azure_openai_api_key="key",
            azure_openai_endpoint=None,
            azure_openai_deployment="gpt-4o",
        )
    )
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        build_llm_gateway()


def test_build_azure_openai_gateway_success():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="azure_openai",
            azure_openai_api_key="key",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_deployment="gpt-4o-mini",
        )
    )
    gateway = build_llm_gateway()
    assert gateway.provider_name == "azure_openai"


def test_build_anthropic_gateway_requires_api_key():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="anthropic",
            anthropic_api_key=None,
        )
    )
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_llm_gateway()


def test_build_anthropic_gateway_success():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="anthropic",
            anthropic_api_key="test-key",
        )
    )
    gateway = build_llm_gateway()
    assert gateway.provider_name == "anthropic"


def test_llm_provider_overrides_legacy_graph_mode():
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            llm_provider="anthropic",
            anthropic_api_key="test-key",
        )
    )
    gateway = get_conversation_llm()
    assert gateway.provider_name == "anthropic"


def test_resolved_provider_defaults_to_openai_when_enabled():
    settings = LLMSettings(graph_llm_mode="enabled", llm_provider="openai", openai_api_key="k")
    assert settings.resolved_provider() == "openai"
