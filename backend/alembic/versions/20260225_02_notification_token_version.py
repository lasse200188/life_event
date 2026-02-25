"""add notification unsubscribe token version

Revision ID: 20260225_02
Revises: 20260225_01
Create Date: 2026-02-25 10:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260225_02"
down_revision = "20260225_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_profiles",
        sa.Column(
            "unsubscribe_token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_profiles", "unsubscribe_token_version")
