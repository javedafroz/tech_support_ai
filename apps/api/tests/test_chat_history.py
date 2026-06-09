import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_agents.runner import SupportGraphRunner
from tech_support_api.db.models import ChatMessage, ChatSession
from tech_support_api.services.chat_service import ChatService
from tech_support_api.services.redis_store import RedisSessionStore


@pytest.mark.asyncio
async def test_load_graph_history_from_redis(
    db_session: AsyncSession,
    redis_store: RedisSessionStore,
):
    session = ChatSession(user_id="test-user@company.com")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    await redis_store.record_turn(
        session.id,
        role="user",
        content="Blue screen on laptop",
        active_ticket_number=None,
        message_count=2,
    )
    await redis_store.record_turn(
        session.id,
        role="assistant",
        content="When did it start?",
        active_ticket_number=None,
        message_count=2,
    )

    service = ChatService(db_session, redis_store)
    history = await service.load_graph_history(session.id, session.user_id)

    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)


@pytest.mark.asyncio
async def test_load_graph_history_postgres_fallback(
    db_session: AsyncSession,
    redis_store: RedisSessionStore,
):
    session = ChatSession(user_id="test-user@company.com")
    db_session.add(session)
    await db_session.flush()

    db_session.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content="Welcome message",
        )
    )
    db_session.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content="Blue screen on laptop",
        )
    )
    await db_session.commit()

    service = ChatService(db_session, redis_store)
    history = await service.load_graph_history(session.id, session.user_id)

    assert len(history) == 2
    contents = [message.content for message in history]
    assert "Welcome message" in contents
    assert "Blue screen on laptop" in contents


@pytest.mark.asyncio
async def test_send_message_passes_hydrated_history_to_graph(
    api_client: AsyncClient,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setenv("GRAPH_ENABLED", "true")
    monkeypatch.setenv("GRAPH_LLM_MODE", "mock")
    from tech_support_api.config import get_settings

    get_settings.cache_clear()

    captured: list[list] = []
    original_invoke = SupportGraphRunner.invoke_turn

    async def spy_invoke(self, **kwargs):
        captured.append(list(kwargs.get("history") or []))
        return await original_invoke(self, **kwargs)

    monkeypatch.setattr(SupportGraphRunner, "invoke_turn", spy_invoke)

    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "I am see blue screen on my laptop"},
        headers=auth_headers,
    )
    await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "It started this morning with error on screen"},
        headers=auth_headers,
    )

    assert len(captured) == 2
    assert len(captured[0]) == 1
    assert isinstance(captured[0][0], AIMessage)
    assert len(captured[1]) >= 2
    assert isinstance(captured[1][0], HumanMessage)
    assert isinstance(captured[1][1], AIMessage)

    get_settings.cache_clear()
