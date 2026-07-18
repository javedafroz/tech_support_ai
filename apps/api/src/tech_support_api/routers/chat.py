import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from tech_support_api.config import get_settings
from tech_support_api.db.models import ChatSession
from tech_support_api.dependencies.auth import require_user_id
from tech_support_api.dependencies.services import get_chat_service
from tech_support_api.schemas.chat import (
    MessageCreate,
    MessageListResponse,
    SendMessageResponse,
    SessionContextResponse,
    SessionContextSchema,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
)
from tech_support_api.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(default=10, ge=1, le=50),
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> SessionListResponse:
    sessions = await chat.list_sessions(user_id, limit=limit)
    return SessionListResponse(sessions=sessions)


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> ChatSession:
    return await chat.create_session(user_id, body)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> ChatSession:
    return await chat.get_session(session_id, user_id)


@router.get("/sessions/{session_id}/context", response_model=SessionContextResponse)
async def get_session_context(
    session_id: UUID,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> SessionContextResponse:
    context = await chat.get_redis_context(session_id, user_id)
    schema = SessionContextSchema.model_validate(context.to_dict()) if context else None
    return SessionContextResponse(session_id=session_id, context=schema)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_messages(
    session_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> MessageListResponse:
    messages, total = await chat.list_messages(session_id, user_id, limit=limit, offset=offset)
    return MessageListResponse(
        messages=messages,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    session_id: UUID,
    body: MessageCreate,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> SendMessageResponse:
    user_message, assistant_message, statuses, intent, _card = await chat.send_message(
        session_id, user_id, body
    )
    return SendMessageResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        system_statuses=statuses,
        detected_intent=intent,
    )


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/sessions/{session_id}/messages/stream")
async def create_message_stream(
    session_id: UUID,
    body: MessageCreate,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    if not get_settings().thought_streaming_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thought streaming is disabled",
        )

    async def event_generator() -> AsyncIterator[str]:
        async for event in chat.send_message_stream(session_id, user_id, body):
            yield _format_sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
