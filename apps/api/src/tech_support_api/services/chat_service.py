from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tech_support_api.db.models import ChatMessage, ChatSession
from tech_support_api.schemas.chat import MessageCreate, MessageResponse, SessionCreate
from tech_support_api.services.graph_service import get_graph_runner, is_graph_enabled
from tech_support_api.services.mock_graph import MockGraphResult, get_mock_graph
from tech_support_api.services.redis_store import (
    RedisSessionStore,
    SessionContext,
    recent_turns_to_langchain,
)

@dataclass(frozen=True)
class GraphExecutionResult:
    assistant_content: str
    system_statuses: list[str]
    detected_intent: str | None
    card: dict | None
    active_ticket_number: str | None


class ChatService:
    def __init__(self, db: AsyncSession, redis_store: RedisSessionStore) -> None:
        self._db = db
        self._redis = redis_store
        self._mock_graph = get_mock_graph()

    async def create_session(self, user_id: str, body: SessionCreate) -> ChatSession:
        session = ChatSession(user_id=user_id, org_id=body.org_id)
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        await self._redis.set_context(
            session.id,
            SessionContext(active_ticket_number=session.active_ticket_number, message_count=0),
        )

        welcome = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=(
                "Hi — I'm your Tech Support assistant. "
                "Describe an issue and I can help prepare a support ticket, "
                "or ask about an existing ticket."
            ),
        )
        self._db.add(welcome)
        await self._db.commit()

        return session

    async def list_sessions(self, user_id: str, *, limit: int = 10) -> list[ChatSession]:
        result = await self._db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.status == "active")
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_session(self, session_id: UUID, user_id: str) -> ChatSession:
        return await self._get_owned_session(session_id, user_id)

    async def list_messages(
        self,
        session_id: UUID,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ChatMessage], int]:
        await self._get_owned_session(session_id, user_id)
        count_result = await self._db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id)
        )
        total = int(count_result.scalar_one())
        result = await self._db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def send_message(
        self,
        session_id: UUID,
        user_id: str,
        body: MessageCreate,
    ) -> tuple[ChatMessage, ChatMessage, list[str], str | None, dict | None]:
        user_message, assistant, graph_result = await self._persist_message_exchange(
            session_id,
            user_id,
            body,
        )
        return (
            user_message,
            assistant,
            graph_result.system_statuses,
            graph_result.detected_intent,
            graph_result.card,
        )

    async def send_message_stream(
        self,
        session_id: UUID,
        user_id: str,
        body: MessageCreate,
    ) -> AsyncIterator[dict[str, Any]]:
        session = await self._get_owned_session(session_id, user_id)
        context = await self._redis.get_context(session_id)
        message_count = context.message_count if context else 0
        history = await self._load_graph_history(session_id)

        user_message = ChatMessage(session_id=session_id, role="user", content=body.content)
        self._db.add(user_message)
        await self._db.flush()

        try:
            graph_result: GraphExecutionResult | None = None
            async for event_type, payload in self._stream_graph_execution(
                session_id=session_id,
                user_id=user_id,
                user_input=body.content,
                message_count=message_count,
                history=history,
            ):
                if event_type == "thought":
                    yield {"type": "thought", "content": payload}
                elif event_type == "complete":
                    graph_result = payload
                    if payload.active_ticket_number:
                        session.active_ticket_number = payload.active_ticket_number

            if graph_result is None:
                yield {"type": "error", "message": "Graph stream ended without a result"}
                return

            assistant = await self._finalize_message_exchange(
                session=session,
                session_id=session_id,
                user_message=user_message,
                user_content=body.content,
                graph_result=graph_result,
            )
            yield {
                "type": "done",
                "user_message": MessageResponse.model_validate(user_message).model_dump(
                    mode="json"
                ),
                "assistant_message": MessageResponse.model_validate(assistant).model_dump(
                    mode="json"
                ),
                "system_statuses": graph_result.system_statuses,
                "detected_intent": graph_result.detected_intent,
            }
        except Exception as exc:
            await self._db.rollback()
            yield {"type": "error", "message": str(exc)}

    async def _persist_message_exchange(
        self,
        session_id: UUID,
        user_id: str,
        body: MessageCreate,
    ) -> tuple[ChatMessage, ChatMessage, GraphExecutionResult]:
        session = await self._get_owned_session(session_id, user_id)
        context = await self._redis.get_context(session_id)
        message_count = context.message_count if context else 0
        history = await self._load_graph_history(session_id)

        user_message = ChatMessage(session_id=session_id, role="user", content=body.content)
        self._db.add(user_message)
        await self._db.flush()

        graph_result = await self._run_graph_execution(
            session=session,
            session_id=session_id,
            user_id=user_id,
            user_input=body.content,
            message_count=message_count,
            history=history,
        )
        assistant = await self._finalize_message_exchange(
            session=session,
            session_id=session_id,
            user_message=user_message,
            user_content=body.content,
            graph_result=graph_result,
        )
        return user_message, assistant, graph_result

    async def _run_graph_execution(
        self,
        *,
        session: ChatSession,
        session_id: UUID,
        user_id: str,
        user_input: str,
        message_count: int,
        history: list,
    ) -> GraphExecutionResult:
        if is_graph_enabled():
            graph_turn = await get_graph_runner().invoke_turn(
                session_id=session_id,
                user_id=user_id,
                user_input=user_input,
                user_email=user_id if "@" in user_id else None,
                message_count=message_count,
                history=history,
            )
            if graph_turn.active_ticket_number:
                session.active_ticket_number = graph_turn.active_ticket_number
            return GraphExecutionResult(
                assistant_content=graph_turn.assistant_content,
                system_statuses=list(graph_turn.system_statuses),
                detected_intent=graph_turn.detected_intent,
                card=graph_turn.card,
                active_ticket_number=graph_turn.active_ticket_number,
            )

        mock_result = self._mock_graph.invoke(user_input, message_count=message_count)
        return self._graph_result_from_mock(mock_result)

    async def _stream_graph_execution(
        self,
        *,
        session_id: UUID,
        user_id: str,
        user_input: str,
        message_count: int,
        history: list,
    ) -> AsyncIterator[tuple[str, Any]]:
        if is_graph_enabled():
            async for event_type, payload in get_graph_runner().astream_turn(
                session_id=session_id,
                user_id=user_id,
                user_input=user_input,
                user_email=user_id if "@" in user_id else None,
                message_count=message_count,
                history=history,
            ):
                if event_type == "complete":
                    graph_turn = payload
                    yield "complete", GraphExecutionResult(
                        assistant_content=graph_turn.assistant_content,
                        system_statuses=list(graph_turn.system_statuses),
                        detected_intent=graph_turn.detected_intent,
                        card=graph_turn.card,
                        active_ticket_number=graph_turn.active_ticket_number,
                    )
                else:
                    yield event_type, payload
            return

        mock_result = self._mock_graph.invoke(user_input, message_count=message_count)
        for status in mock_result.system_statuses:
            yield "thought", status
            await asyncio.sleep(0)
        yield "complete", self._graph_result_from_mock(mock_result)

    @staticmethod
    def _graph_result_from_mock(mock_result: MockGraphResult) -> GraphExecutionResult:
        return GraphExecutionResult(
            assistant_content=mock_result.assistant_content,
            system_statuses=list(mock_result.system_statuses),
            detected_intent=mock_result.detected_intent,
            card=mock_result.card,
            active_ticket_number=None,
        )

    async def _finalize_message_exchange(
        self,
        *,
        session: ChatSession,
        session_id: UUID,
        user_message: ChatMessage,
        user_content: str,
        graph_result: GraphExecutionResult,
    ) -> ChatMessage:
        for status_label in graph_result.system_statuses:
            self._db.add(
                ChatMessage(
                    session_id=session_id,
                    role="system",
                    content=status_label,
                )
            )

        assistant = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=graph_result.assistant_content,
            card=graph_result.card,
        )
        self._db.add(assistant)
        session.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(user_message)
        await self._db.refresh(assistant)

        count_result = await self._db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id)
        )
        new_count = int(count_result.scalar_one())

        await self._redis.record_turn(
            session_id,
            role="user",
            content=user_content,
            active_ticket_number=session.active_ticket_number,
            message_count=new_count,
        )
        await self._redis.record_turn(
            session_id,
            role="assistant",
            content=assistant.content or "",
            active_ticket_number=session.active_ticket_number,
            message_count=new_count,
        )
        return assistant

    async def get_redis_context(self, session_id: UUID, user_id: str) -> SessionContext | None:
        await self._get_owned_session(session_id, user_id)
        return await self._redis.get_context(session_id)

    async def load_graph_history(self, session_id: UUID, user_id: str) -> list:
        await self._get_owned_session(session_id, user_id)
        return await self._load_graph_history(session_id)

    async def _load_graph_history(self, session_id: UUID) -> list:
        memory = await self._redis.get_memory(session_id)
        if memory and memory.recent_turns:
            return recent_turns_to_langchain(memory.recent_turns)

        result = await self._db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role.in_(["user", "assistant"]),
            )
            .order_by(ChatMessage.created_at.asc())
        )
        turns = [
            {"role": message.role, "content": message.content or ""}
            for message in result.scalars().all()
        ]
        return recent_turns_to_langchain(turns)

    async def _get_owned_session(self, session_id: UUID, user_id: str) -> ChatSession:
        from fastapi import HTTPException, status

        result = await self._db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return session
