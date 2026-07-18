"""Deterministic mock LLM for tests and offline development."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import BaseMessage, HumanMessage

from tech_support_orchestration.models import IntentName, StructuredIntent

from tech_support_agents.conversation_analysis import ConversationTurn
from tech_support_agents.llm_gateway import TroubleshootOutcomeLabel
from tech_support_agents.rag_guidance import TroubleshootGuidance, TroubleshootStepGuidance


class MockConversationLLM:
    """Deterministic stand-in for unit tests and local dev without external LLM APIs."""

    provider_name = "mock"

    UNSUPPORTED_HINT = re.compile(r"\b(unsupported|no\s+match|cannot\s+help)\b", re.I)

    CREATE_PATTERN = re.compile(
        r"\b(vpn|email|password|broken|not working|issue|problem|error|blue screen|bsod)\b",
        re.I,
    )
    HARDWARE_PATTERN = re.compile(r"\b(blue screen|bsod|laptop|pc ran into a problem)\b", re.I)

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
        return self._propose_intent_sync(
            user_text,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
            message_count=message_count,
            history=history,
        )

    def _propose_intent_sync(
        self,
        user_text: str,
        *,
        session_id: UUID,
        user_id: str,
        user_email: str | None,
        message_count: int,
        history: list[BaseMessage] | None = None,
    ) -> ConversationTurn:
        text = user_text.strip()
        combined = self._combined_user_text(user_text, history)
        is_support_issue = bool(self.CREATE_PATTERN.search(combined))
        problem_summary = combined[:280] if is_support_issue else None

        if len(text.split()) <= 3 and text.lower().rstrip("]") in {"hi", "hello", "hey"}:
            return ConversationTurn(
                structured_intent=None,
                reply=(
                    "Hi — I can help you create or check support tickets. "
                    "What issue are you experiencing?"
                ),
                is_support_issue=False,
                problem_summary=None,
            )

        if self._has_enough_create_context(combined) and message_count >= 1:
            email = user_email or f"{user_id}@company.com"
            category = (
                "hardware"
                if self.HARDWARE_PATTERN.search(combined)
                else ("network" if "vpn" in combined.lower() else "software")
            )
            intent = StructuredIntent(
                intent=IntentName.CREATE_TICKET,
                confidence=0.91,
                session_id=session_id,
                user_id=user_id,
                payload={
                    "title": combined[:80],
                    "description": combined,
                    "customer_email": email,
                    "suggested_category": category,
                    "suggested_priority": "high" if "urgent" in combined.lower() else "normal",
                },
                timestamp=datetime.now(UTC),
            )
            return ConversationTurn(
                structured_intent=intent,
                reply=None,
                is_support_issue=is_support_issue,
                problem_summary=problem_summary,
            )

        if self.CREATE_PATTERN.search(combined):
            return ConversationTurn(
                structured_intent=None,
                reply=(
                    "I can help with that. Please share a bit more detail — "
                    "what you see, when it started, and any error messages."
                ),
                is_support_issue=True,
                problem_summary=problem_summary,
            )

        return ConversationTurn(
            structured_intent=None,
            reply=(
                "Thanks for the update. Describe your issue in a few sentences "
                "and I can prepare a support ticket for you."
            ),
            is_support_issue=False,
            problem_summary=None,
        )

    @staticmethod
    def _combined_user_text(user_text: str, history: list[BaseMessage] | None) -> str:
        parts = []
        for message in history or []:
            if isinstance(message, HumanMessage):
                parts.append(str(message.content))
        parts.append(user_text.strip())
        return " ".join(part for part in parts if part)

    @classmethod
    def _has_enough_create_context(cls, combined: str) -> bool:
        lowered = combined.lower()
        has_problem = bool(cls.CREATE_PATTERN.search(combined))
        has_timing_or_impact = any(
            token in lowered
            for token in (
                "morning",
                "today",
                "yesterday",
                "started",
                "since",
                "error",
                "not working",
                "restart",
                "ran into a problem",
            )
        )
        return has_problem and has_timing_or_impact and len(combined) > 40

    async def generate_troubleshoot_guidance(
        self,
        problem: str,
        contexts: list[dict[str, str]],
        *,
        history: list[BaseMessage] | None = None,
        max_steps: int = 5,
    ) -> TroubleshootGuidance:
        del history
        if not contexts or self.UNSUPPORTED_HINT.search(problem):
            return TroubleshootGuidance(supported=False, intro="", steps=[])

        source_ids = [c["source_id"] for c in contexts if c.get("source_id")]
        primary = source_ids[0] if source_ids else "src1"
        # Adaptive: one step for short context, up to two when multiple sources exist.
        bodies = [(c.get("body") or "").strip() for c in contexts]
        first_body = bodies[0] if bodies else "Follow the guidance from the retrieved handbook."
        steps = [
            TroubleshootStepGuidance(
                instruction=_mock_instruction(first_body),
                source_ids=[primary],
            )
        ]
        if len(contexts) > 1 and max_steps > 1 and bodies[1]:
            steps.append(
                TroubleshootStepGuidance(
                    instruction=_mock_instruction(bodies[1]),
                    source_ids=[source_ids[1] if len(source_ids) > 1 else primary],
                )
            )
        steps = steps[:max_steps]
        display = problem.strip()
        if len(display) > 120:
            display = display[:117].rstrip() + "…"
        intro = (
            f"I'm sorry you're dealing with {display[0].lower() + display[1:]}. "
            "That can be frustrating — let's try a few quick steps:"
            if display
            else "I'm sorry you're running into this — that can be frustrating. Let's try a few quick steps:"
        )
        return TroubleshootGuidance(
            supported=True,
            intro=intro,
            steps=steps,
            follow_up=(
                "Give that a try and let me know if it worked. "
                "If it's still not resolved, say so and I'll open a ticket for you."
            ),
        )

    async def classify_troubleshoot_outcome(
        self,
        user_text: str,
        *,
        history: list[BaseMessage] | None = None,
    ) -> TroubleshootOutcomeLabel:
        del history
        lowered = user_text.lower()
        if any(token in lowered for token in ("ticket", "human", "escalate", "agent")):
            return "escalate"
        if any(token in lowered for token in ("fixed", "resolved", "worked", "sorted", "good now")):
            return "resolved"
        if any(token in lowered for token in ("still", "broken", "not working", "failed", "no luck")):
            return "failed"
        return "unclear"


def _mock_instruction(body: str) -> str:
    cleaned = re.sub(r"\s+", " ", body).strip()
    if len(cleaned) > 280:
        cleaned = cleaned[:277].rstrip() + "…"
    return cleaned or "Try the recommended check from the handbook."
