from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeSettings(BaseModel):
    """Runtime settings for KB / RAG (env-backed)."""

    kb_rag_enabled: bool = False
    vector_backend: str = "qdrant"  # qdrant | memory
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "agent_handbook"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    retrieval_top_k: int = 5
    min_score: float = 0.35
    max_troubleshoot_steps: int = 5
    rag_max_context_chars: int = 12000
    include_chat_transcript_in_ticket: bool = True
    pdf_to_markdown_converter: str = "docling"
    chunk_strategy: str = "page"  # page | heading
    chunk_max_chars: int = 4000
    chunk_overlap_chars: int = 200

    @classmethod
    def from_env(cls) -> KnowledgeSettings:
        return cls(
            kb_rag_enabled=_env_bool("KB_RAG_ENABLED", False),
            vector_backend=os.environ.get("VECTOR_BACKEND", "qdrant").lower(),
            qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.environ.get("QDRANT_API_KEY") or None,
            qdrant_collection=os.environ.get("QDRANT_COLLECTION", "agent_handbook"),
            embedding_provider=os.environ.get("EMBEDDING_PROVIDER", "openai"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1536")),
            retrieval_top_k=int(os.environ.get("KB_RETRIEVAL_TOP_K", "5")),
            min_score=float(os.environ.get("KB_MIN_SCORE", "0.35")),
            max_troubleshoot_steps=int(os.environ.get("KB_MAX_TROUBLESHOOT_STEPS", "5")),
            rag_max_context_chars=int(os.environ.get("KB_RAG_MAX_CONTEXT_CHARS", "12000")),
            include_chat_transcript_in_ticket=_env_bool(
                "KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET", True
            ),
            pdf_to_markdown_converter=os.environ.get(
                "PDF_TO_MARKDOWN_CONVERTER", "docling"
            ).lower(),
            chunk_strategy=os.environ.get("KB_CHUNK_STRATEGY", "page").lower(),
            chunk_max_chars=int(os.environ.get("KB_CHUNK_MAX_CHARS", "4000")),
            chunk_overlap_chars=int(os.environ.get("KB_CHUNK_OVERLAP_CHARS", "200")),
        )


class ChunkHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    score: float
    title: str
    section_title: str | None = None
    body: str
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkRecord(BaseModel):
    """Point written to the vector store during ingest."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    title: str
    section_title: str | None = None
    body: str
    embedding: list[float]
    status: str = "published"
    embedding_model: str
    version: int = 1
    category_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
