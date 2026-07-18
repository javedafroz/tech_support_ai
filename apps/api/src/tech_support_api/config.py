from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_env: str = "development"
    database_url: str = "postgresql+asyncpg://techsupport:techsupport@localhost:5433/techsupport"
    database_url_sync: str = "postgresql://techsupport:techsupport@localhost:5433/techsupport"
    redis_url: str = "redis://localhost:6380/0"
    redis_session_ttl_seconds: int = 86400
    auth_mode: str = "dev"  # dev | jwt
    auth_dev_header_user_id: str = "X-User-Id"
    auth_jwt_secret: str | None = None
    auth_jwt_algorithms: list[str] = ["HS256"]
    auth_jwt_audience: str | None = None
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    graph_enabled: bool = False
    graph_llm_mode: str = "mock"  # mock | openai (legacy enable flag)
    llm_provider: str = "openai"  # openai | azure_openai | anthropic
    graph_checkpoint: bool = False
    thought_streaming_enabled: bool = False
    ticketing_provider: str = "zammad"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-02-15-preview"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_temperature: float = 0.2
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "attachments"
    s3_region: str = "us-east-1"
    attachment_max_bytes: int = 10 * 1024 * 1024
    attachment_max_per_message: int = 5

    # KB / RAG
    kb_rag_enabled: bool = False
    vector_backend: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "agent_handbook"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    kb_retrieval_top_k: int = 5
    kb_min_score: float = 0.35
    kb_max_troubleshoot_steps: int = 5
    kb_rag_max_context_chars: int = 12000
    kb_include_chat_transcript_in_ticket: bool = True
    pdf_to_markdown_converter: str = "docling"
    kb_chunk_strategy: str = "page"  # page | heading
    kb_chunk_max_chars: int = 4000
    kb_chunk_overlap_chars: int = 200
    kb_handbook_s3_bucket: str = "agent-handbooks"
    kb_handbook_storage_backend: str = "memory"
    ceph_rgw_endpoint: str | None = None
    ceph_rgw_access_key: str | None = None
    ceph_rgw_secret_key: str | None = None
    ceph_rgw_region: str = "us-east-1"
    ceph_rgw_addressing_style: str = "auto"

    # Keycloak (admin only)
    keycloak_url: str = "http://localhost:8081"
    keycloak_realm: str = "tech-support"
    keycloak_admin_client_id: str = "tech-support-admin"
    keycloak_api_audience: str = "tech-support-admin"
    keycloak_jwks_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
