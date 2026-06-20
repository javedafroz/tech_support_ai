from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import BaseMessage

from tech_support_agents.graph import compile_support_graph

StreamEventKind = Literal["thought", "complete"]


@dataclass
class GraphTurnResult:
    assistant_content: str
    system_statuses: list[str] = field(default_factory=list)
    detected_intent: str | None = None
    card: dict | None = None
    active_ticket_number: str | None = None
    provider_response: dict | None = None
    error: str | None = None


class SupportGraphRunner:
    def __init__(self, graph) -> None:
        self._graph = graph

    @classmethod
    def compile(cls, *, checkpointer=None) -> SupportGraphRunner:
        return cls(compile_support_graph(checkpointer=checkpointer))

    def _initial_state(
        self,
        *,
        session_id: UUID,
        user_id: str,
        user_input: str,
        user_email: str | None,
        message_count: int,
        history: list[BaseMessage] | None,
    ) -> dict[str, Any]:
        initial_state: dict[str, Any] = {
            "session_id": str(session_id),
            "user_id": user_id,
            "user_email": user_email,
            "user_input": user_input,
            "message_count": message_count,
            "system_statuses": [],
        }
        if history:
            initial_state["messages"] = list(history)
        return initial_state

    @staticmethod
    def _result_from_state(final_state: dict[str, Any]) -> GraphTurnResult:
        intent = final_state.get("structured_intent")
        return GraphTurnResult(
            assistant_content=final_state.get("assistant_reply")
            or _last_ai_content(final_state),
            system_statuses=list(final_state.get("system_statuses", [])),
            detected_intent=intent.intent.value if intent else None,
            card=final_state.get("ui_card"),
            active_ticket_number=final_state.get("active_ticket_number"),
            provider_response=final_state.get("provider_response"),
            error=final_state.get("error"),
        )

    async def invoke_turn(
        self,
        *,
        session_id: UUID,
        user_id: str,
        user_input: str,
        user_email: str | None = None,
        message_count: int = 0,
        history: list[BaseMessage] | None = None,
    ) -> GraphTurnResult:
        config = {"configurable": {"thread_id": str(session_id)}}
        initial_state = self._initial_state(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            user_email=user_email,
            message_count=message_count,
            history=history,
        )
        final_state = await self._graph.ainvoke(initial_state, config=config)
        return self._result_from_state(final_state)

    async def astream_turn(
        self,
        *,
        session_id: UUID,
        user_id: str,
        user_input: str,
        user_email: str | None = None,
        message_count: int = 0,
        history: list[BaseMessage] | None = None,
    ) -> AsyncIterator[tuple[StreamEventKind, Any]]:
        config = {"configurable": {"thread_id": str(session_id)}}
        initial_state = self._initial_state(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            user_email=user_email,
            message_count=message_count,
            history=history,
        )
        prev_len = 0
        final_state: dict[str, Any] | None = None
        async for state in self._graph.astream(initial_state, config=config, stream_mode="values"):
            final_state = state
            statuses = list(state.get("system_statuses", []))
            for status in statuses[prev_len:]:
                yield "thought", status
            prev_len = len(statuses)
        if final_state is not None:
            yield "complete", self._result_from_state(final_state)


def _last_ai_content(state: dict) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if content:
            return str(content)
    return "I could not generate a response."
