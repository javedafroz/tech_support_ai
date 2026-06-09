"""Graph invoke endpoint — LangGraph when enabled, mock graph otherwise."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from tech_support_api.dependencies.auth import require_user_id
from tech_support_api.dependencies.services import get_chat_service
from tech_support_api.services.chat_service import ChatService
from tech_support_api.services.graph_service import get_graph_runner, is_graph_enabled
from tech_support_api.services.mock_graph import MockGraphResult, get_mock_graph

router = APIRouter(prefix="/chat", tags=["graph"])


class GraphInvokeRequest(BaseModel):
    content: str = Field(min_length=1, max_length=16000)


class GraphInvokeResponse(BaseModel):
    assistant_content: str
    system_statuses: list[str]
    detected_intent: str | None = None
    card: dict | None = None


@router.post("/sessions/{session_id}/graph/invoke", response_model=GraphInvokeResponse)
async def invoke_graph(
    session_id: UUID,
    body: GraphInvokeRequest,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> GraphInvokeResponse:
    """Stateless graph turn — use POST .../messages to persist in chat history."""
    await chat.get_session(session_id, user_id)
    context = await chat.get_redis_context(session_id, user_id)
    message_count = context.message_count if context else 0
    history = await chat.load_graph_history(session_id, user_id)

    if is_graph_enabled():
        turn = await get_graph_runner().invoke_turn(
            session_id=session_id,
            user_id=user_id,
            user_input=body.content,
            user_email=user_id if "@" in user_id else None,
            message_count=message_count,
            history=history,
        )
        return GraphInvokeResponse(
            assistant_content=turn.assistant_content,
            system_statuses=turn.system_statuses,
            detected_intent=turn.detected_intent,
            card=turn.card,
        )

    result: MockGraphResult = get_mock_graph().invoke(
        body.content,
        message_count=message_count,
    )
    return GraphInvokeResponse(
        assistant_content=result.assistant_content,
        system_statuses=result.system_statuses,
        detected_intent=result.detected_intent,
        card=result.card,
    )
