from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile
from tech_support_api.dependencies.keycloak_auth import ROLE_ADMIN, ROLE_EDITOR, AdminPrincipal
from tech_support_api.services.kb_service import KbService
from tech_support_knowledge import configure_knowledge
from tech_support_knowledge.models import KnowledgeSettings
from tech_support_knowledge.store import reset_knowledge_store_cache


@pytest.fixture
def kb_env(monkeypatch):
    monkeypatch.setenv("KB_HANDBOOK_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("VECTOR_BACKEND", "memory")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "64")
    configure_knowledge(
        KnowledgeSettings(
            vector_backend="memory",
            embedding_provider="hash",
            embedding_dimensions=64,
            min_score=0.0,
        )
    )
    reset_knowledge_store_cache()
    yield
    reset_knowledge_store_cache()


def _upload(filename: str, content: bytes, content_type: str) -> StarletteUploadFile:
    return StarletteUploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_kb_upload_ingest_publish_and_search(db_session: AsyncSession, kb_env) -> None:
    del kb_env
    principal = AdminPrincipal(
        subject=str(uuid4()),
        username="kb-admin",
        email="kb-admin@local",
        roles=frozenset({ROLE_EDITOR, ROLE_ADMIN}),
    )
    service = KbService(db_session)
    markdown = b"""# Outlook sync

## Step 1

Sign out of Outlook and sign back in.
"""
    doc = await service.create_from_upload(
        principal=principal,
        file=_upload("outlook.md", markdown, "text/markdown"),
        title="Outlook guide",
        org_id="default",
        category_tags=["email"],
        auto_ingest=True,
    )
    assert doc.status == "draft"
    assert doc.chunk_count and doc.chunk_count >= 1

    preview = await service.get_markdown_preview(doc.id)
    assert "Outlook" in preview

    # Draft chunks are not searchable
    draft_hits = await service.search_preview(query="Outlook sign out", top_k=5)
    assert draft_hits == []

    published = await service.publish(doc.id, principal=principal)
    assert published.status == "published"
    assert published.published_at is not None

    hits = await service.search_preview(query="Outlook sign out", top_k=5, min_score=0.0)
    assert hits
    assert hits[0]["document_id"] == doc.id
