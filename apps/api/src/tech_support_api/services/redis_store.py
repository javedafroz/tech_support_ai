"""Redis hot-state for chat sessions (context + recent turn window)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from tech_support_api.config import get_settings


@dataclass
class SessionContext:
    active_ticket_number: str | None = None
    last_message_at: str | None = None
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionContext:
        return cls(
            active_ticket_number=data.get("active_ticket_number"),
            last_message_at=data.get("last_message_at"),
            message_count=int(data.get("message_count", 0)),
        )


@dataclass
class SessionMemory:
    """Rolling window of recent turns for fast graph hydrate (Sprint 6+)."""

    recent_turns: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"recent_turns": self.recent_turns}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMemory:
        return cls(recent_turns=list(data.get("recent_turns", [])))


class RedisSessionStore:
    MAX_RECENT_TURNS = 20

    def __init__(self, client: redis.Redis) -> None:
        settings = get_settings()
        self._client = client
        self._ttl = settings.redis_session_ttl_seconds

    def _context_key(self, session_id: UUID | str) -> str:
        return f"session:{session_id}:context"

    def _memory_key(self, session_id: UUID | str) -> str:
        return f"session:{session_id}:memory"

    async def get_context(self, session_id: UUID) -> SessionContext | None:
        raw = await self._client.get(self._context_key(session_id))
        if not raw:
            return None
        return SessionContext.from_dict(json.loads(raw))

    async def set_context(self, session_id: UUID, context: SessionContext) -> None:
        await self._client.set(
            self._context_key(session_id),
            json.dumps(context.to_dict()),
            ex=self._ttl,
        )

    async def get_memory(self, session_id: UUID) -> SessionMemory | None:
        raw = await self._client.get(self._memory_key(session_id))
        if not raw:
            return None
        return SessionMemory.from_dict(json.loads(raw))

    async def set_memory(self, session_id: UUID, memory: SessionMemory) -> None:
        await self._client.set(
            self._memory_key(session_id),
            json.dumps(memory.to_dict()),
            ex=self._ttl,
        )

    async def record_turn(
        self,
        session_id: UUID,
        *,
        role: str,
        content: str,
        active_ticket_number: str | None,
        message_count: int,
    ) -> SessionContext:
        now = datetime.now(UTC).isoformat()
        context = SessionContext(
            active_ticket_number=active_ticket_number,
            last_message_at=now,
            message_count=message_count,
        )
        await self.set_context(session_id, context)

        memory = await self.get_memory(session_id) or SessionMemory()
        memory.recent_turns.append({"role": role, "content": content[:500]})
        memory.recent_turns = memory.recent_turns[-self.MAX_RECENT_TURNS :]
        await self.set_memory(session_id, memory)
        return context

    async def ping(self) -> bool:
        return bool(await self._client.ping())


_redis_client: redis.Redis | None = None
_store: RedisSessionStore | None = None


async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_redis_store() -> RedisSessionStore:
    global _store
    if _store is None:
        _store = RedisSessionStore(await get_redis_client())
    return _store


async def close_redis() -> None:
    global _redis_client, _store
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except RuntimeError:
            pass
        _redis_client = None
    _store = None
