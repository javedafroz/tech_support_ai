"""Fixtures for live OpenAI + Zammad integration tests (no mocks)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from playwright.async_api import Page, async_playwright
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tech_support_agents.llm import LLMSettings, configure_llm
from tech_support_api.config import get_settings
from tech_support_api.db.base import Base
from tech_support_api.db.session import get_db
from tech_support_api.main import app
from tech_support_api.services import graph_service
from tech_support_api.services.redis_store import (
    RedisSessionStore,
    close_redis,
    get_redis_store,
)
from tech_support_zammad import ZammadClient

from tests.integration.env_loader import (
    integration_env_bool,
    load_project_env,
    require_live_credentials,
)
from tests.integration.live_stack import LiveStack
from tests.integration.log import configure_live_integration_logging

logger = logging.getLogger(__name__)

# Load .env before fixtures read INTEGRATION_* settings (IDE runs may skip session fixtures).
load_project_env()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: integration tests requiring OpenAI and Zammad credentials",
    )
    config.addinivalue_line(
        "markers",
        "live_ui: browser-based live integration (visible Chromium window)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    marker_expr = config.getoption("-m") or ""
    if "live" in marker_expr or "live_ui" in marker_expr:
        return
    skip = pytest.mark.skip(reason="Live tests — run: make test-live or make test-live-ui")
    for item in items:
        if "live" in item.keywords or "live_ui" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def live_credentials() -> tuple[str, str, str, str]:
    try:
        return require_live_credentials()
    except RuntimeError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def live_user_email(live_credentials: tuple[str, str, str, str]) -> str:
    return live_credentials[3]


@pytest.fixture(scope="session")
def configure_live_stack(live_credentials: tuple[str, str, str, str]) -> None:
    configure_live_integration_logging()
    load_project_env()
    _, zammad_url, zammad_token, _ = live_credentials

    os.environ["GRAPH_ENABLED"] = "true"
    os.environ["GRAPH_LLM_MODE"] = "openai"
    os.environ["AUTH_MODE"] = "dev"
    os.environ["ZAMMAD_BASE_URL"] = zammad_url
    os.environ["ZAMMAD_API_TOKEN"] = zammad_token

    get_settings.cache_clear()
    settings = get_settings()
    configure_llm(
        LLMSettings(
            graph_llm_mode="openai",
            openai_api_key=settings.openai_api_key or os.environ["OPENAI_API_KEY"],
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
        )
    )
    graph_service._runner = None


@pytest.fixture
async def db_engine(configure_live_stack):
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://techsupport:techsupport@localhost:5433/techsupport",
    )
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def live_api_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_store = RedisSessionStore(redis_client)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def override_get_redis_store() -> RedisSessionStore:
        return redis_store

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_store] = override_get_redis_store

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await redis_client.flushdb()
    await redis_client.aclose()
    await close_redis()
    graph_service._runner = None


@pytest.fixture
def live_auth_headers(live_user_email: str) -> dict[str, str]:
    return {"X-User-Id": live_user_email}


@pytest.fixture(scope="session")
def user_simulator(live_credentials: tuple[str, str, str, str]):
    from tests.integration.user_sim import OpenAIUserSimulator

    openai_key, _, _, _ = live_credentials
    settings = get_settings()
    return OpenAIUserSimulator(
        api_key=openai_key,
        model=os.environ.get("USER_SIM_MODEL") or settings.openai_model,
        base_url=settings.openai_base_url,
    )


@pytest.fixture(scope="session")
def zammad_client(live_credentials: tuple[str, str, str, str]) -> ZammadClient:
    _, zammad_url, zammad_token, _ = live_credentials
    return ZammadClient(zammad_url, zammad_token)


@pytest.fixture(scope="session")
def live_stack(configure_live_stack) -> Generator[LiveStack, None, None]:
    stack = LiveStack()
    stack.start()
    yield stack
    stack.stop()


@pytest.fixture
async def browser_page(configure_live_stack) -> AsyncGenerator[Page, None]:
    # live_ui tests default to a visible browser; set INTEGRATION_HEADLESS=true to hide it.
    headless = integration_env_bool("INTEGRATION_HEADLESS", default=False)
    slow_mo = int(os.environ.get("INTEGRATION_SLOW_MO", "0"))
    logger.info("Launching Chromium for live_ui (headless=%s, slow_mo=%sms)", headless, slow_mo)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()
