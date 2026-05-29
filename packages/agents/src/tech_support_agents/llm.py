"""LLM factory — mock for tests; OpenAI for production conversation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from tech_support_orchestration.models import IntentName, StructuredIntent


@dataclass(frozen=True)
class LLMSettings:
    graph_llm_mode: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None

    @classmethod
    def from_env(cls) -> LLMSettings:
        return cls(
            graph_llm_mode=os.environ.get("GRAPH_LLM_MODE", "mock").lower(),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            openai_base_url=os.environ.get("OPENAI_BASE_URL"),
        )


_settings: LLMSettings = LLMSettings.from_env()


def configure_llm(settings: LLMSettings) -> None:
    """Apply API settings to the agents package (call from FastAPI lifespan)."""
    global _settings
    _settings = settings
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_model:
        os.environ["OPENAI_MODEL"] = settings.openai_model
    if settings.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
    os.environ["GRAPH_LLM_MODE"] = settings.graph_llm_mode


def get_llm_settings() -> LLMSettings:
    return _settings


class MockConversationLLM:
    """Deterministic stand-in for unit tests and local dev without OpenAI."""

    CREATE_PATTERN = re.compile(
        r"\b(vpn|email|password|broken|not working|issue|problem|error)\b",
        re.I,
    )

    def propose_intent(
        self,
        user_text: str,
        *,
        session_id: UUID,
        user_id: str,
        user_email: str | None,
        message_count: int,
    ) -> tuple[StructuredIntent | None, str | None]:
        text = user_text.strip()

        if len(text.split()) <= 3 and text.lower() in {"hi", "hello", "hey"}:
            return None, (
                "Hi — I can help you create or check support tickets. "
                "What issue are you experiencing?"
            )

        if self.CREATE_PATTERN.search(text) and message_count >= 1 and len(text) > 40:
            email = user_email or f"{user_id}@company.com"
            intent = StructuredIntent(
                intent=IntentName.CREATE_TICKET,
                confidence=0.91,
                session_id=session_id,
                user_id=user_id,
                payload={
                    "title": text[:80],
                    "description": text,
                    "customer_email": email,
                    "suggested_category": "network" if "vpn" in text.lower() else "software",
                    "suggested_priority": "high" if "urgent" in text.lower() else "normal",
                },
                timestamp=datetime.now(UTC),
            )
            return intent, None

        if self.CREATE_PATTERN.search(text):
            return None, (
                "I can help with that. Please share a bit more detail — "
                "what you see, when it started, and any error messages."
            )

        return None, (
            "Thanks for the update. Describe your issue in a few sentences "
            "and I can prepare a support ticket for you."
        )


def get_conversation_llm(mode: str | None = None):
    settings = get_llm_settings()
    selected = (mode or settings.graph_llm_mode).lower()

    if selected == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when GRAPH_LLM_MODE=openai. "
                "Set it in .env or disable OpenAI mode."
            )
        from tech_support_agents.openai_llm import OpenAIConversationLLM

        return OpenAIConversationLLM(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    return MockConversationLLM()
