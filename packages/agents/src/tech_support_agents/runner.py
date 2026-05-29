from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from tech_support_agents.graph import compile_support_graph


@dataclass
class GraphTurnResult:
    assistant_content: str
    system_statuses: list[str] = field(default_factory=list)
    detected_intent: str | None = None
    card: dict | None = None
    active_ticket_number: str | None = None
    zammad_response: dict | None = None
    error: str | None = None


class SupportGraphRunner:
    def __init__(self, graph) -> None:
        self._graph = graph

    @classmethod
    def compile(cls, *, checkpointer=None) -> SupportGraphRunner:
        return cls(compile_support_graph(checkpointer=checkpointer))

    async def invoke_turn(
        self,
        *,
        session_id: UUID,
        user_id: str,
        user_input: str,
        user_email: str | None = None,
        message_count: int = 0,
    ) -> GraphTurnResult:
        config = {"configurable": {"thread_id": str(session_id)}}
        final_state = await self._graph.ainvoke(
            {
                "session_id": str(session_id),
                "user_id": user_id,
                "user_email": user_email,
                "user_input": user_input,
                "message_count": message_count,
                "system_statuses": [],
            },
            config=config,
        )

        intent = final_state.get("structured_intent")
        return GraphTurnResult(
            assistant_content=final_state.get("assistant_reply")
            or _last_ai_content(final_state),
            system_statuses=list(final_state.get("system_statuses", [])),
            detected_intent=intent.intent.value if intent else None,
            card=final_state.get("ui_card"),
            active_ticket_number=final_state.get("active_ticket_number"),
            zammad_response=final_state.get("zammad_response"),
            error=final_state.get("error"),
        )


def _last_ai_content(state: dict) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if content:
            return str(content)
    return "I could not generate a response."
