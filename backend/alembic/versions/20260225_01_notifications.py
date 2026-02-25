"""add notification profiles and outbox

Revision ID: 20260225_01
Revises: 20260224_01
Create Date: 2026-02-25 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260225_01"
down_revision = "20260224_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("email_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="de-DE"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Berlin"),
        sa.Column(
            "reminder_due_soon_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("max_reminders_per_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribe_token_hash", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_notification_profiles_plan_id"),
    )
    op.create_index(
        "ix_notification_profiles_sendable",
        "notification_profiles",
        ["email_consent", "reminder_due_soon_enabled"],
        unique=False,
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key_raw", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=32), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["profile_id"], ["notification_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key_raw", name="uq_notification_outbox_dedupe_key_raw"),
    )
    op.create_index(
        "ix_notification_outbox_status_next_attempt",
        "notification_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_profile_created",
        "notification_outbox",
        ["profile_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_profile_created", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status_next_attempt", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_index("ix_notification_profiles_sendable", table_name="notification_profiles")
    op.drop_table("notification_profiles")
