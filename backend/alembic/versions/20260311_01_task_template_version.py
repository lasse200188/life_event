"""add task_template_version to tasks

Revision ID: 20260311_01
Revises: 20260225_02
Create Date: 2026-03-11 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260311_01"
down_revision = "20260225_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "task_template_version", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.alter_column("tasks", "task_template_version", server_default=None)


def downgrade() -> None:
    op.drop_column("tasks", "task_template_version")
