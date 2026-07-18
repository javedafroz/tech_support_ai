"""Add KB handbook metadata tables (documents, ingest jobs, deflection events)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    # Idempotent: pytest Base.metadata.create_all may have created these already.
    if not _table_exists("kb_documents"):
        op.create_table(
            "kb_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", sa.String(length=255), nullable=True, index=True),
            sa.Column("title", sa.String(length=512), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("category_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("source_content_type", sa.String(length=128), nullable=False),
            sa.Column("object_key", sa.String(length=1024), nullable=False),
            sa.Column("derived_markdown_object_key", sa.String(length=1024), nullable=True),
            sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("embedding_model", sa.String(length=128), nullable=True),
            sa.Column("qdrant_collection", sa.String(length=128), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=True),
            sa.Column("converter_name", sa.String(length=64), nullable=True),
            sa.Column("converter_version", sa.String(length=64), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("updated_by", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("org_id", "slug", name="uq_kb_documents_org_slug"),
        )
    if not _table_exists("kb_ingest_jobs"):
        op.create_table(
            "kb_ingest_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="CASCADE"),
        )
    if not _table_exists("kb_deflection_events"):
        op.create_table(
            "kb_deflection_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("steps_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="SET NULL"),
        )


def downgrade() -> None:
    if _table_exists("kb_deflection_events"):
        op.drop_table("kb_deflection_events")
    if _table_exists("kb_ingest_jobs"):
        op.drop_table("kb_ingest_jobs")
    if _table_exists("kb_documents"):
        op.drop_table("kb_documents")
