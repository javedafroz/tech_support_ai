import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tech_support_agents.llm import LLMSettings, configure_llm
from tech_support_knowledge import KnowledgeSettings, configure_knowledge
from tech_support_ticketing import configure_ticketing, merge_ticketing_settings

from tech_support_api import __version__
from tech_support_api.config import get_settings
from tech_support_api.routers import admin_analytics, admin_kb, attachments, chat, config, graph, health
from tech_support_api.services.graph_service import init_graph_runner
from tech_support_api.services.redis_store import close_redis

logger = logging.getLogger(__name__)


def _llm_settings_from_api() -> LLMSettings:
    settings = get_settings()
    return LLMSettings(
        graph_llm_mode=settings.graph_llm_mode,
        llm_provider=settings.llm_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        openai_base_url=settings.openai_base_url,
        azure_openai_api_key=settings.azure_openai_api_key,
        azure_openai_endpoint=settings.azure_openai_endpoint,
        azure_openai_deployment=settings.azure_openai_deployment,
        azure_openai_api_version=settings.azure_openai_api_version,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
        llm_temperature=settings.llm_temperature,
    )


def _configure_llm_from_settings() -> None:
    llm_settings = _llm_settings_from_api()
    configure_llm(llm_settings)
    if not get_settings().graph_enabled:
        return

    provider = llm_settings.resolved_provider()
    if provider is None:
        logger.info("LangGraph conversation LLM: mock")
        return

    error = llm_settings.configuration_error(provider)
    if error:
        raise RuntimeError(f"{error} Set credentials in .env or use GRAPH_LLM_MODE=mock.")

    if provider == "openai":
        logger.info("LangGraph conversation LLM: OpenAI (%s)", llm_settings.openai_model)
    elif provider == "azure_openai":
        logger.info(
            "LangGraph conversation LLM: Azure OpenAI (%s)",
            llm_settings.azure_openai_deployment,
        )
    elif provider == "anthropic":
        logger.info(
            "LangGraph conversation LLM: Anthropic (%s)",
            llm_settings.anthropic_model,
        )


def _configure_knowledge_from_settings() -> None:
    settings = get_settings()
    configure_knowledge(
        KnowledgeSettings(
            kb_rag_enabled=settings.kb_rag_enabled,
            vector_backend=settings.vector_backend,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            qdrant_collection=settings.qdrant_collection,
            embedding_provider=settings.embedding_provider,
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            retrieval_top_k=settings.kb_retrieval_top_k,
            min_score=settings.kb_min_score,
            max_troubleshoot_steps=settings.kb_max_troubleshoot_steps,
            rag_max_context_chars=settings.kb_rag_max_context_chars,
            include_chat_transcript_in_ticket=settings.kb_include_chat_transcript_in_ticket,
            pdf_to_markdown_converter=settings.pdf_to_markdown_converter,
            chunk_strategy=settings.kb_chunk_strategy,
            chunk_max_chars=settings.kb_chunk_max_chars,
            chunk_overlap_chars=settings.kb_chunk_overlap_chars,
        )
    )
    if settings.kb_rag_enabled:
        logger.info(
            "KB/RAG enabled (vector=%s collection=%s)",
            settings.vector_backend,
            settings.qdrant_collection,
        )


def _configure_ticketing_from_settings() -> None:
    settings = get_settings()
    configure_ticketing(merge_ticketing_settings(provider=settings.ticketing_provider))
    logger.info("Ticketing provider: %s", settings.ticketing_provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_llm_from_settings()
    _configure_ticketing_from_settings()
    _configure_knowledge_from_settings()
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
    app.include_router(config.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(attachments.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(admin_kb.router, prefix="/api/v1")
    app.include_router(admin_analytics.router, prefix="/api/v1")
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
