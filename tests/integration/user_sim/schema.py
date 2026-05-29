"""Structured output schema for the AI User Simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DoneReason = Literal["ticket_created", "gave_up", "blocked"]


class UserSimTurn(BaseModel):
    """One simulated user turn — internal to integration tests only."""

    model_config = ConfigDict(extra="forbid")

    reply_to_support: str = Field(
        description="Next chat message to send to IT support (empty if conversation_done)"
    )
    conversation_done: bool = Field(
        description="True when the simulated user should stop sending messages"
    )
    done_reason: DoneReason | None = Field(
        default=None,
        description="Why the conversation ended (internal test log)",
    )
    notes: str | None = Field(
        default=None,
        description="Internal tester notes — never sent to the support API",
    )


@dataclass
class ConversationTurn:
    turn_index: int
    user_message: str
    assistant_content: str
    assistant_card: dict | None
    detected_intent: str | None
    system_statuses: list[str] = field(default_factory=list)


@dataclass
class ConversationResult:
    session_id: str
    ticket_number: str | None
    ticket_id: int | None
    turns_used: int
    run_reference: str
    transcript: list[ConversationTurn]
    success: bool
    failure_reason: str | None = None
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_artifact_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "ticket_number": self.ticket_number,
            "ticket_id": self.ticket_id,
            "turns_used": self.turns_used,
            "run_reference": self.run_reference,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "completed_at": self.completed_at,
            "transcript": [
                {
                    "turn": t.turn_index,
                    "user": t.user_message,
                    "assistant": t.assistant_content,
                    "card": t.assistant_card,
                    "intent": t.detected_intent,
                    "system_statuses": t.system_statuses,
                }
                for t in self.transcript
            ],
        }
