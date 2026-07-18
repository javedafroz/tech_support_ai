"""Vector store protocol and factories for Agent Handbook retrieval."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol
from uuid import UUID

from tech_support_knowledge.models import ChunkHit, ChunkRecord, KnowledgeSettings


class KnowledgeStore(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None: ...

    def delete_by_document(self, document_id: UUID) -> None: ...

    def set_document_status(self, document_id: UUID, status: str) -> int: ...

    def retrieve(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        min_score: float,
    ) -> list[ChunkHit]: ...


class MemoryKnowledgeStore:
    """In-process store for unit tests (no Qdrant)."""

    def __init__(self) -> None:
        self._chunks: dict[UUID, ChunkRecord] = {}

    def ensure_collection(self) -> None:
        return None

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

    def delete_by_document(self, document_id: UUID) -> None:
        to_delete = [
            chunk_id
            for chunk_id, chunk in self._chunks.items()
            if chunk.document_id == document_id
        ]
        for chunk_id in to_delete:
            del self._chunks[chunk_id]

    def set_document_status(self, document_id: UUID, status: str) -> int:
        updated = 0
        for chunk in self._chunks.values():
            if chunk.document_id == document_id:
                chunk.status = status
                updated += 1
        return updated

    def retrieve(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        min_score: float,
    ) -> list[ChunkHit]:
        scored: list[tuple[float, ChunkRecord]] = []
        for chunk in self._chunks.values():
            if chunk.status != "published":
                continue
            score = _cosine_similarity(query_embedding, chunk.embedding)
            if score >= min_score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits: list[ChunkHit] = []
        for score, chunk in scored[:top_k]:
            hits.append(
                ChunkHit(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    score=score,
                    title=chunk.title,
                    section_title=chunk.section_title,
                    body=chunk.body,
                    chunk_index=chunk.chunk_index,
                    metadata=dict(chunk.metadata),
                )
            )
        return hits


class QdrantKnowledgeStore:
    def __init__(self, settings: KnowledgeSettings) -> None:
        from qdrant_client import QdrantClient

        self._settings = settings
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            check_compatibility=False,
        )
        self._collection = settings.qdrant_collection

    def ensure_collection(self) -> None:
        from qdrant_client.http import models as qmodels

        names = {c.name for c in self._client.get_collections().collections}
        if self._collection in names:
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qmodels.VectorParams(
                size=self._settings.embedding_dimensions,
                distance=qmodels.Distance.COSINE,
            ),
        )
        for field in ("document_id", "status"):
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        from qdrant_client.http import models as qmodels

        if not chunks:
            return
        self.ensure_collection()
        points = [
            qmodels.PointStruct(
                id=str(chunk.chunk_id),
                vector=chunk.embedding,
                payload={
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "title": chunk.title,
                    "section_title": chunk.section_title,
                    "body": chunk.body,
                    "status": chunk.status,
                    "embedding_model": chunk.embedding_model,
                    "version": chunk.version,
                    "category_tags": chunk.category_tags,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def delete_by_document(self, document_id: UUID) -> None:
        from qdrant_client.http import models as qmodels

        self.ensure_collection()
        self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )

    def set_document_status(self, document_id: UUID, status: str) -> int:
        from qdrant_client.http import models as qmodels

        self.ensure_collection()
        doc_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=str(document_id)),
                )
            ]
        )
        count = self._client.count(
            collection_name=self._collection,
            count_filter=doc_filter,
            exact=True,
        ).count
        if count:
            self._client.set_payload(
                collection_name=self._collection,
                payload={"status": status},
                points=doc_filter,
                wait=True,
            )
        return int(count)

    def retrieve(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        min_score: float,
    ) -> list[ChunkHit]:
        from qdrant_client.http import models as qmodels

        self.ensure_collection()
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_embedding,
            limit=top_k,
            score_threshold=min_score,
            with_payload=True,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="status",
                        match=qmodels.MatchValue(value="published"),
                    )
                ]
            ),
        )
        hits: list[ChunkHit] = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                ChunkHit(
                    chunk_id=UUID(str(point.id)),
                    document_id=UUID(str(payload["document_id"])),
                    score=float(point.score),
                    title=str(payload.get("title") or ""),
                    section_title=payload.get("section_title"),
                    body=str(payload.get("body") or ""),
                    chunk_index=int(payload.get("chunk_index") or 0),
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k
                        not in {
                            "document_id",
                            "chunk_index",
                            "title",
                            "section_title",
                            "body",
                            "status",
                        }
                    },
                )
            )
        return hits


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_settings: KnowledgeSettings | None = None


def configure_knowledge(settings: KnowledgeSettings) -> None:
    global _settings
    _settings = settings
    reset_knowledge_store_cache()


def get_knowledge_settings() -> KnowledgeSettings:
    global _settings
    if _settings is None:
        _settings = KnowledgeSettings.from_env()
    return _settings


@lru_cache
def get_knowledge_store() -> KnowledgeStore:
    settings = get_knowledge_settings()
    if settings.vector_backend == "memory":
        return MemoryKnowledgeStore()
    return QdrantKnowledgeStore(settings)


def reset_knowledge_store_cache() -> None:
    get_knowledge_store.cache_clear()
