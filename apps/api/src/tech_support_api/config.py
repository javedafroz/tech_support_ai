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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    graph_enabled: bool = False
    graph_llm_mode: str = "mock"  # mock | openai
    graph_checkpoint: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
