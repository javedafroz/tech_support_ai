"""Ingest pipeline: source bytes → Markdown → chunks → embeddings → Qdrant."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from tech_support_storage import ObjectStorage

from tech_support_knowledge.chunking import chunk_markdown
from tech_support_knowledge.converters import get_pdf_converter
from tech_support_knowledge.embeddings import Embedder, get_embedder
from tech_support_knowledge.models import ChunkRecord, KnowledgeSettings
from tech_support_knowledge.store import KnowledgeStore, get_knowledge_settings, get_knowledge_store


@dataclass(frozen=True)
class IngestResult:
    markdown: str
    chunk_count: int
    converter_name: str | None
    converter_version: str | None
    derived_markdown_object_key: str | None
    embedding_model: str
    checksum_sha256: str


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.strip().lower()).strip("-")
    return slug[:200] or "handbook"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_markdown(
    *,
    source_bytes: bytes,
    content_type: str,
    filename: str,
    converter_name: str,
) -> tuple[str, str | None, str | None]:
    """Return (markdown, converter_name, converter_version)."""
    lowered = content_type.lower()
    name = filename.lower()
    if lowered in {"text/markdown", "text/x-markdown"} or name.endswith(".md"):
        return source_bytes.decode("utf-8"), None, None
    if lowered == "application/pdf" or name.endswith(".pdf"):
        result = get_pdf_converter(converter_name).convert(source_bytes, filename=filename)
        return result.markdown, result.converter_name, result.converter_version
    raise ValueError(
        f"Unsupported handbook type: {content_type or filename}. "
        "Accepted: application/pdf, text/markdown"
    )


def ingest_document(
    *,
    document_id: UUID,
    title: str,
    source_bytes: bytes,
    content_type: str,
    filename: str,
    version: int,
    category_tags: list[str] | None = None,
    status: str = "published",
    storage: ObjectStorage,
    org_id: str = "default",
    object_key: str,
    store: KnowledgeStore | None = None,
    embedder: Embedder | None = None,
    settings: KnowledgeSettings | None = None,
) -> IngestResult:
    settings = settings or get_knowledge_settings()
    store = store or get_knowledge_store()
    embedder = embedder or get_embedder(settings)

    checksum = sha256_hex(source_bytes)
    markdown, converter_name, converter_version = resolve_markdown(
        source_bytes=source_bytes,
        content_type=content_type,
        filename=filename,
        converter_name=settings.pdf_to_markdown_converter,
    )

    derived_key: str | None = None
    if converter_name:
        derived_key = object_key.rsplit("/", 1)[0] + "/derived.md"
        storage.put_object(
            key=derived_key,
            data=markdown.encode("utf-8"),
            content_type="text/markdown",
        )

    chunks = chunk_markdown(
        markdown,
        strategy=settings.chunk_strategy,
        max_chars=settings.chunk_max_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    if not chunks:
        store.delete_by_document(document_id)
        return IngestResult(
            markdown=markdown,
            chunk_count=0,
            converter_name=converter_name,
            converter_version=converter_version,
            derived_markdown_object_key=derived_key,
            embedding_model=embedder.model,
            checksum_sha256=checksum,
        )

    embeddings = embedder.embed_documents([c.body for c in chunks])
    records = [
        ChunkRecord(
            chunk_id=uuid4(),
            document_id=document_id,
            chunk_index=chunk.index,
            title=title,
            section_title=chunk.section_title,
            body=chunk.body,
            embedding=embeddings[i],
            status=status,
            embedding_model=embedder.model,
            version=version,
            category_tags=list(category_tags or []),
            metadata={
                "org_id": org_id,
                "source_filename": filename,
                **({"page": chunk.page} if chunk.page is not None else {}),
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    store.delete_by_document(document_id)
    store.upsert_chunks(records)

    return IngestResult(
        markdown=markdown,
        chunk_count=len(records),
        converter_name=converter_name,
        converter_version=converter_version,
        derived_markdown_object_key=derived_key,
        embedding_model=embedder.model,
        checksum_sha256=checksum,
    )
