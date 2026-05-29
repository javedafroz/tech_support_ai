"""Mock LangGraph for M1 (Sprint 4) — replaced by real graph in Sprint 5."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# User-facing labels per UI/UX strategy §7.3
STATUS_CHECKING = "Checking your request…"
STATUS_APPLYING_RULES = "Applying support rules…"
STATUS_THINKING = "Thinking…"


@dataclass
class MockGraphResult:
    assistant_content: str
    system_statuses: list[str] = field(default_factory=list)
    detected_intent: str | None = None
    card: dict | None = None


class MockSupportGraph:
    """Rule-based mock conversation agent until LangGraph is wired (Sprint 5)."""

    GREETING_PATTERN = re.compile(r"^(hi|hello|hey)\b", re.I)
    STATUS_PATTERN = re.compile(r"\b(status|ticket\s*#?|check\s+my)\b", re.I)
    CREATE_PATTERN = re.compile(
        r"\b(help|issue|problem|broken|not working|vpn|email|password|login|error)\b",
        re.I,
    )

    def invoke(self, user_text: str, *, message_count: int = 0) -> MockGraphResult:
        text = user_text.strip()
        statuses = [STATUS_THINKING, STATUS_CHECKING]

        if self.GREETING_PATTERN.search(text) and len(text.split()) <= 4:
            return MockGraphResult(
                assistant_content=(
                    "Hi — I can help you create or check support tickets. "
                    "Describe your issue and I'll guide you through the next steps."
                ),
                system_statuses=statuses,
                detected_intent="ChitChat",
            )

        if self.STATUS_PATTERN.search(text):
            return MockGraphResult(
                assistant_content=(
                    "I can look up your ticket status once the full workflow is connected. "
                    "For now, share your ticket number (e.g. #22019) or a short description "
                    "of the issue and I'll confirm what I understood."
                ),
                system_statuses=[*statuses, STATUS_APPLYING_RULES],
                detected_intent="CheckStatus",
            )

        if self.CREATE_PATTERN.search(text):
            return self._create_ticket_intake(text, message_count)

        if message_count <= 2:
            return MockGraphResult(
                assistant_content=(
                    "Thanks for reaching out. Could you tell me a bit more — "
                    "what isn't working, and when did it start?"
                ),
                system_statuses=statuses,
                detected_intent="Clarify",
            )

        return MockGraphResult(
            assistant_content=(
                "I've noted that. In the next release I'll create or update your ticket "
                "in the support system automatically. For now, keep describing any details "
                "that would help support — device, error messages, and impact."
            ),
            system_statuses=statuses,
            detected_intent="General",
        )

    def _create_ticket_intake(self, text: str, message_count: int) -> MockGraphResult:
        statuses = [STATUS_THINKING, STATUS_CHECKING, STATUS_APPLYING_RULES]
        if message_count < 2:
            return MockGraphResult(
                assistant_content=(
                    "I can help with that. Are you seeing any error message, "
                    "and is this affecting just you or multiple people?"
                ),
                system_statuses=statuses,
                detected_intent="CreateTicket",
            )

        title = text[:80] + ("…" if len(text) > 80 else "")
        return MockGraphResult(
            assistant_content=(
                f"Understood — **{title}**. "
                "When ticket creation is enabled, I'll show a summary for you to confirm "
                "before creating the ticket in your organization's support system."
            ),
            system_statuses=statuses,
            detected_intent="CreateTicket",
            card={
                "card_type": "ticket_summary",
                "title": title,
                "description": text,
                "suggested_category": "Network" if "vpn" in text.lower() else "Software",
                "suggested_priority": "high" if "urgent" in text.lower() else "normal",
            },
        )


_default_graph = MockSupportGraph()


def get_mock_graph() -> MockSupportGraph:
    return _default_graph
