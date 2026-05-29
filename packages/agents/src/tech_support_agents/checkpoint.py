from __future__ import annotations

from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def postgres_checkpointer(database_url_sync: str):
    """Async Postgres checkpointer for LangGraph (Sprint 5)."""
    async with AsyncPostgresSaver.from_conn_string(database_url_sync) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
