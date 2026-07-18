from __future__ import annotations

from uuid import uuid4

from tech_support_knowledge.embeddings import HashEmbedder
from tech_support_knowledge.handbook_storage import handbook_object_key
from tech_support_knowledge.ingest import ingest_document, slugify
from tech_support_knowledge.models import KnowledgeSettings
from tech_support_knowledge.store import MemoryKnowledgeStore
from tech_support_storage import MemoryStorage


def test_slugify() -> None:
    assert slugify("VPN / AnyConnect Guide!") == "vpn-anyconnect-guide"


def test_ingest_markdown_roundtrip_searchable() -> None:
    storage = MemoryStorage()
    store = MemoryKnowledgeStore()
    embedder = HashEmbedder(dimensions=32)
    settings = KnowledgeSettings(
        vector_backend="memory",
        embedding_provider="hash",
        embedding_dimensions=32,
        min_score=0.1,
    )
    doc_id = uuid4()
    key = handbook_object_key(
        org_id="default",
        document_id=str(doc_id),
        version=1,
        filename="vpn.md",
    )
    markdown = """# VPN

## Step 1

Quit AnyConnect and reconnect.

## Step 2

Clear the VPN cache folder.
"""
    source = markdown.encode("utf-8")
    storage.put_object(key=key, data=source, content_type="text/markdown")

    result = ingest_document(
        document_id=doc_id,
        title="VPN guide",
        source_bytes=source,
        content_type="text/markdown",
        filename="vpn.md",
        version=1,
        category_tags=["network"],
        status="published",
        storage=storage,
        object_key=key,
        store=store,
        embedder=embedder,
        settings=settings,
    )
    assert result.chunk_count >= 2
    assert result.converter_name is None
    assert result.derived_markdown_object_key is None

    query = embedder.embed_query("AnyConnect disconnect clear cache")
    hits = store.retrieve(query, top_k=3, min_score=0.0)
    assert hits
    assert hits[0].document_id == doc_id
