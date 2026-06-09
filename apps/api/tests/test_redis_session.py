from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from tech_support_api.services.redis_store import (
    RedisSessionStore,
    SessionContext,
    recent_turns_to_langchain,
)


@pytest.mark.asyncio
async def test_redis_context_round_trip(redis_store: RedisSessionStore):
    session_id = uuid4()
    context = SessionContext(active_ticket_number="22019", message_count=2)
    await redis_store.set_context(session_id, context)
    loaded = await redis_store.get_context(session_id)
    assert loaded is not None
    assert loaded.active_ticket_number == "22019"
    assert loaded.message_count == 2


@pytest.mark.asyncio
async def test_record_turn_appends_memory(redis_store: RedisSessionStore):
    session_id = uuid4()
    await redis_store.record_turn(
        session_id,
        role="user",
        content="VPN not working",
        active_ticket_number=None,
        message_count=1,
    )
    memory = await redis_store.get_memory(session_id)
    assert memory is not None
    assert len(memory.recent_turns) == 1
    assert memory.recent_turns[0]["role"] == "user"


def test_recent_turns_to_langchain_maps_roles():
    messages = recent_turns_to_langchain(
        [
            {"role": "user", "content": "Blue screen on laptop"},
            {"role": "assistant", "content": "When did it start?"},
            {"role": "system", "content": "Thinking…"},
        ]
    )
    assert len(messages) == 2
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
