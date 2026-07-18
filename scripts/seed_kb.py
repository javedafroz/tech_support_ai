"""Seed the Agent Handbook KB from local markdown files.

Ingests and publishes every ``*.md`` under ``config/knowledge/`` into the same
Postgres + vector store the API/chat uses, so the Phase 2 troubleshoot flow has
something to retrieve. Idempotent: an existing handbook with the same slug is
replaced.

Prerequisites (see .env):
  - KB_RAG_ENABLED=true, VECTOR_BACKEND=qdrant, QDRANT_URL reachable
  - EMBEDDING_PROVIDER=openai with OPENAI_API_KEY set (or EMBEDDING_PROVIDER=hash)

Usage:
  .venv/bin/python scripts/seed_kb.py       (or: make seed-kb)
"""

from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path

from sqlalchemy import select
from starlette.datastructures import Headers, UploadFile
from tech_support_api.config import get_settings
from tech_support_api.db.models import KbDocument
from tech_support_api.db.session import async_session_factory
from tech_support_api.dependencies.keycloak_auth import AdminPrincipal
from tech_support_api.main import _configure_knowledge_from_settings
from tech_support_api.services.kb_service import KbService
from tech_support_knowledge.ingest import slugify

KNOWLEDGE_DIR = Path("config/knowledge")
ORG_ID = "default"
PRINCIPAL = AdminPrincipal(
    subject="seed-script",
    username="seed",
    email=None,
    roles=frozenset({"kb_admin"}),
)


async def _seed_file(path: Path) -> None:
    title = re.sub(r"\.[^.]+$", "", path.name)
    slug = slugify(title)
    data = path.read_bytes()

    async with async_session_factory() as db:
        service = KbService(db)
        existing = (
            await db.execute(
                select(KbDocument).where(
                    KbDocument.org_id == ORG_ID,
                    KbDocument.slug == slug,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await service.delete_document(existing.id, principal=PRINCIPAL)

        upload = UploadFile(
            filename=path.name,
            file=io.BytesIO(data),
            headers=Headers({"content-type": "text/markdown"}),
        )
        doc = await service.create_from_upload(
            principal=PRINCIPAL,
            file=upload,
            title=None,
            org_id=ORG_ID,
            category_tags=[],
            auto_ingest=True,
        )
        published = await service.publish(doc.id, principal=PRINCIPAL)
        print(
            f"  seeded '{path.name}' -> doc={doc.id} "
            f"chunks={doc.chunk_count} status={published.status}"
        )


async def main() -> None:
    settings = get_settings()
    _configure_knowledge_from_settings()

    print(
        f"KB seed: vector_backend={settings.vector_backend} "
        f"embedding={settings.embedding_provider}/{settings.embedding_model} "
        f"collection={settings.qdrant_collection} kb_rag_enabled={settings.kb_rag_enabled}"
    )
    if not settings.kb_rag_enabled:
        print("  WARNING: KB_RAG_ENABLED is not true — chat will not use the handbook flow.")
    if settings.vector_backend == "memory":
        print(
            "  WARNING: VECTOR_BACKEND=memory is process-local; the API won't see "
            "seeded data. Use VECTOR_BACKEND=qdrant."
        )

    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not files:
        print(f"  No markdown handbooks found in {KNOWLEDGE_DIR}/")
        return

    for path in files:
        try:
            await _seed_file(path)
        except Exception as exc:  # noqa: BLE001 - surface per-file errors, keep going
            print(f"  FAILED '{path.name}': {exc}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
