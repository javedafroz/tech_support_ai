import os
from collections.abc import AsyncGenerator

import pytest
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tech_support_api.config import get_settings
from tech_support_api.db.base import Base
from tech_support_api.db.session import get_db
from tech_support_api.main import app
from tech_support_api.services.redis_store import (
    RedisSessionStore,
    close_redis,
    get_redis_store,
)

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://techsupport:techsupport@localhost:5433/techsupport",
)
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")


@pytest.fixture(autouse=True)
def _reset_auth_settings(monkeypatch):
    from tech_support_agents.llm import LLMSettings, configure_llm

    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("GRAPH_ENABLED", "false")
    monkeypatch.setenv("GRAPH_LLM_MODE", "mock")
    monkeypatch.setenv("THOUGHT_STREAMING_ENABLED", "false")
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    configure_llm(LLMSettings(graph_llm_mode="mock"))
    yield
    get_settings.cache_clear()
    configure_llm(LLMSettings(graph_llm_mode="mock"))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def api_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    redis_store = RedisSessionStore(redis_client)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def override_get_redis_store() -> RedisSessionStore:
        return redis_store

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_store] = override_get_redis_store
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await redis_client.flushdb()
    await redis_client.aclose()
    await close_redis()


@pytest.fixture
async def redis_store():
    await close_redis()
    client = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    store = RedisSessionStore(client)
    yield store
    await client.flushdb()
    await client.aclose()
    await close_redis()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-User-Id": "test-user@company.com"}
