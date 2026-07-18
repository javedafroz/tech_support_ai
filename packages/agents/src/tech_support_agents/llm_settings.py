"""LLM package settings — mirrors ticketing provider configuration pattern."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

SUPPORTED_LLM_PROVIDERS = frozenset({"openai", "azure_openai", "anthropic"})


@dataclass(frozen=True)
class LLMSettings:
    graph_llm_mode: str = "mock"
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-02-15-preview"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_temperature: float = 0.2

    @classmethod
    def from_env(cls) -> LLMSettings:
        return cls(
            graph_llm_mode=os.environ.get("GRAPH_LLM_MODE", "mock").lower(),
            llm_provider=os.environ.get("LLM_PROVIDER", "openai").strip().lower(),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            openai_base_url=os.environ.get("OPENAI_BASE_URL"),
            azure_openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            azure_openai_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            azure_openai_api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
            ),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            llm_temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        )

    def resolved_provider(self) -> str | None:
        """Return provider name when LLM is enabled, or None for mock mode."""
        mode = self.graph_llm_mode.lower()
        if mode == "mock":
            return None
        if self.llm_provider in SUPPORTED_LLM_PROVIDERS:
            return self.llm_provider
        if mode in SUPPORTED_LLM_PROVIDERS:
            return mode
        return "openai"

    def configuration_error(self, provider: str | None = None) -> str | None:
        selected = provider or self.resolved_provider()
        if selected is None:
            return None
        if selected == "openai":
            if not self.openai_api_key:
                return "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
            return None
        if selected == "azure_openai":
            missing = [
                name
                for name, value in (
                    ("AZURE_OPENAI_API_KEY", self.azure_openai_api_key),
                    ("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint),
                    ("AZURE_OPENAI_DEPLOYMENT", self.azure_openai_deployment),
                )
                if not value
            ]
            if missing:
                return (
                    f"{', '.join(missing)} required when LLM_PROVIDER=azure_openai"
                )
            return None
        if selected == "anthropic":
            if not self.anthropic_api_key:
                return "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            return None
        return f"Unsupported LLM provider: {selected}"


_settings: LLMSettings = LLMSettings.from_env()


def configure_llm(settings: LLMSettings) -> None:
    """Apply settings to the agents package (call from FastAPI lifespan)."""
    global _settings
    _settings = settings
    os.environ["GRAPH_LLM_MODE"] = settings.graph_llm_mode
    os.environ["LLM_PROVIDER"] = settings.llm_provider
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_model:
        os.environ["OPENAI_MODEL"] = settings.openai_model
    if settings.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
    if settings.azure_openai_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = settings.azure_openai_api_key
    if settings.azure_openai_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = settings.azure_openai_endpoint
    if settings.azure_openai_deployment:
        os.environ["AZURE_OPENAI_DEPLOYMENT"] = settings.azure_openai_deployment
    os.environ["AZURE_OPENAI_API_VERSION"] = settings.azure_openai_api_version
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.anthropic_model:
        os.environ["ANTHROPIC_MODEL"] = settings.anthropic_model


def get_llm_settings() -> LLMSettings:
    return _settings


def merge_llm_settings(**overrides) -> LLMSettings:
    current = LLMSettings.from_env()
    return replace(current, **{k: v for k, v in overrides.items() if v is not None})
