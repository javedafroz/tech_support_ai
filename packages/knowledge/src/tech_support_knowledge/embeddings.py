"""Embedding providers for handbook ingest and retrieval."""

from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

from tech_support_knowledge.models import KnowledgeSettings


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic local embedder for tests / offline ingest.

    Token-hashed vectors so shared words yield higher cosine similarity.
    """

    def __init__(self, *, model: str = "hash-embedder", dimensions: int = 64) -> None:
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
        tokens = [t for t in normalized.split() if t] or ["empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dimensions):
                values[i] += (digest[i % len(digest)] / 255.0) * 2.0 - 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class OpenAIEmbedder:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict = {"model": self.model, "input": texts}
        if self.model.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.dimensions
        response = self._client.embeddings.create(**kwargs)
        # Preserve input order
        by_index = {item.index: item.embedding for item in response.data}
        return [list(by_index[i]) for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedder(settings: KnowledgeSettings | None = None) -> Embedder:
    settings = settings or KnowledgeSettings.from_env()
    provider = settings.embedding_provider.lower()
    if provider in {"hash", "memory", "mock"}:
        return HashEmbedder(dimensions=min(settings.embedding_dimensions, 256))

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embedding_provider=openai")
        return OpenAIEmbedder(
            api_key=api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )

    if provider == "azure_openai":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or settings.embedding_model
        if not api_key or not endpoint:
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT are required "
                "for embedding_provider=azure_openai"
            )
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        base = endpoint.rstrip("/") + f"/openai/deployments/{deployment}"
        return OpenAIEmbedder(
            api_key=api_key,
            model=deployment,
            dimensions=settings.embedding_dimensions,
            base_url=f"{base}?api-version={api_version}",
        )

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")
