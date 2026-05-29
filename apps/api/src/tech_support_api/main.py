from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging

from tech_support_agents.llm import LLMSettings, configure_llm
from tech_support_api import __version__
from tech_support_api.config import get_settings
from tech_support_api.routers import chat, graph, health
from tech_support_api.services.graph_service import init_graph_runner
from tech_support_api.services.redis_store import close_redis

logger = logging.getLogger(__name__)


def _configure_llm_from_settings() -> None:
    settings = get_settings()
    configure_llm(
        LLMSettings(
            graph_llm_mode=settings.graph_llm_mode,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
        )
    )
    if (
        settings.graph_enabled
        and settings.graph_llm_mode.lower() == "openai"
        and not settings.openai_api_key
    ):
        raise RuntimeError(
            "GRAPH_LLM_MODE=openai requires OPENAI_API_KEY. "
            "Set OPENAI_API_KEY in .env or use GRAPH_LLM_MODE=mock."
        )
    if settings.graph_enabled and settings.graph_llm_mode.lower() == "openai":
        logger.info("LangGraph conversation LLM: OpenAI (%s)", settings.openai_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_llm_from_settings()
    await init_graph_runner()
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tech Support AI API",
        version=__version__,
        description="Web chat backend for Zammad-integrated support automation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "tech_support_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_env == "development",
    )


if __name__ == "__main__":
    run()
