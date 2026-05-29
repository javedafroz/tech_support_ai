from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tech_support_api.db.models import ChatMessage, ChatSession
from tech_support_api.schemas.chat import MessageCreate, SessionCreate
from tech_support_api.services.graph_service import get_graph_runner, is_graph_enabled
from tech_support_api.services.mock_graph import get_mock_graph
from tech_support_api.services.redis_store import RedisSessionStore, SessionContext


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
        session = await self._get_owned_session(session_id, user_id)
        context = await self._redis.get_context(session_id)
        message_count = context.message_count if context else 0

        user_message = ChatMessage(session_id=session_id, role="user", content=body.content)
        self._db.add(user_message)
        await self._db.flush()

        if is_graph_enabled():
            graph_turn = await get_graph_runner().invoke_turn(
                session_id=session_id,
                user_id=user_id,
                user_input=body.content,
                user_email=user_id if "@" in user_id else None,
                message_count=message_count,
            )
            graph_result = type(
                "R",
                (),
                {
                    "assistant_content": graph_turn.assistant_content,
                    "system_statuses": graph_turn.system_statuses,
                    "detected_intent": graph_turn.detected_intent,
                    "card": graph_turn.card,
                },
            )()
            if graph_turn.active_ticket_number:
                session.active_ticket_number = graph_turn.active_ticket_number
        else:
            graph_result = self._mock_graph.invoke(body.content, message_count=message_count)

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
            content=body.content,
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

        return (
            user_message,
            assistant,
            graph_result.system_statuses,
            graph_result.detected_intent,
            graph_result.card,
        )

    async def get_redis_context(self, session_id: UUID, user_id: str) -> SessionContext | None:
        await self._get_owned_session(session_id, user_id)
        return await self._redis.get_context(session_id)

    async def _get_owned_session(self, session_id: UUID, user_id: str) -> ChatSession:
        from fastapi import HTTPException, status

        result = await self._db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return session
