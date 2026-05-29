"""policy_audit_log, zammad_operations, reason_code_messages

Revision ID: 002
Revises: 001
Create Date: 2026-05-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASON_CODE_SEEDS = [
    ("MISSING_TITLE", "Please provide a short summary of your issue."),
    ("MISSING_DESCRIPTION", "Please describe what happened so we can create a ticket."),
    ("MISSING_CUSTOMER_EMAIL", "We need your email to link this ticket to your account."),
    ("INVALID_INTENT_SCHEMA", "We couldn't process that request. Please try rephrasing."),
    ("LOW_CONFIDENCE", "I'm not sure I understood. Could you clarify what you need?"),
    ("TICKET_ACCESS_DENIED", "You don't have access to that ticket."),
    ("TICKET_NOT_FOUND", "I couldn't find a matching ticket on your account."),
    ("TICKET_STATE_INVALID", "That ticket can't be updated in its current state."),
    ("ATTACHMENT_TYPE_BLOCKED", "That file type isn't allowed."),
    ("ATTACHMENT_SIZE_EXCEEDED", "That file is too large."),
    ("ATTACHMENT_COUNT_EXCEEDED", "Too many attachments for this ticket."),
    ("ESCALATION_NOT_ALLOWED", "This ticket can't be escalated further in chat."),
    ("RATE_LIMIT_EXCEEDED", "Please wait a moment before sending another message."),
    ("DUPLICATE_TICKET_SUSPECTED", "You may already have an open ticket for this issue."),
    (
        "ZAMMAD_UNAVAILABLE",
        "Support ticketing is temporarily unavailable. Your request may be queued.",
    ),
    ("INTERNAL_ERROR", "Something went wrong. Please try again or use your usual support channel."),
]


def upgrade() -> None:
    op.create_table(
        "policy_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intent", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("rule_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_policy_audit_log_session_id", "policy_audit_log", ["session_id"])

    op.create_table(
        "zammad_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_type", sa.String(64), nullable=False),
        sa.Column("command", postgresql.JSONB(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_zammad_operations_session_id", "zammad_operations", ["session_id"])

    op.create_table(
        "reason_code_messages",
        sa.Column("reason_code", sa.String(64), primary_key=True),
        sa.Column("locale", sa.String(8), primary_key=True, server_default="en"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    reason_table = sa.table(
        "reason_code_messages",
        sa.column("reason_code", sa.String),
        sa.column("locale", sa.String),
        sa.column("message", sa.Text),
    )
    op.bulk_insert(
        reason_table,
        [{"reason_code": code, "locale": "en", "message": msg} for code, msg in REASON_CODE_SEEDS],
    )


def downgrade() -> None:
    op.drop_table("reason_code_messages")
    op.drop_index("ix_zammad_operations_session_id", table_name="zammad_operations")
    op.drop_table("zammad_operations")
    op.drop_index("ix_policy_audit_log_session_id", table_name="policy_audit_log")
    op.drop_table("policy_audit_log")
