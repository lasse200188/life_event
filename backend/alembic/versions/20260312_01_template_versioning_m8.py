"""template versioning catalog and plan template metadata

Revision ID: 20260312_01
Revises: 20260311_01
Create Date: 2026-03-12 00:30:00
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260312_01"
down_revision = "20260311_01"
branch_labels = None
depends_on = None


def _derive_key(template_id: str, version: int) -> str:
    return f"{template_id}/v{version}"


def _read_compiled_and_hash(template_id: str, version: int) -> tuple[dict, str]:
    root = Path(__file__).resolve().parents[3]
    path = root / "workflows" / template_id / f"v{version}" / "compiled.json"
    if not path.exists():
        raise RuntimeError(f"Missing workflow file for backfill: {path}")

    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Invalid workflow JSON for backfill: {path}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Workflow root must be object for backfill: {path}")
    if payload.get("template_id") != template_id:
        raise RuntimeError(
            f"Workflow template_id mismatch in {path}: {payload.get('template_id')!r}"
        )
    if payload.get("version") != version:
        raise RuntimeError(
            f"Workflow version mismatch in {path}: {payload.get('version')!r}"
        )

    digest = hashlib.sha256(raw).hexdigest()
    return payload, digest


def upgrade() -> None:
    op.create_table(
        "template_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compiled_hash", sa.String(length=64), nullable=True),
        sa.Column("changelog_md", sa.Text(), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "version", name="uq_template_versions_id_version"
        ),
        sa.UniqueConstraint("template_key", name="uq_template_versions_key"),
    )
    op.create_index(
        "ix_template_versions_template_id",
        "template_versions",
        ["template_id"],
        unique=False,
    )

    op.add_column("plans", sa.Column("template_id", sa.Text(), nullable=True))
    op.add_column("plans", sa.Column("template_version", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("upgraded_from_plan_id", sa.Uuid(), nullable=True))
    op.create_index("ix_plans_template_id", "plans", ["template_id"], unique=False)
    op.create_foreign_key(
        "fk_plans_upgraded_from_plan_id",
        "plans",
        "plans",
        ["upgraded_from_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )

    conn = op.get_bind()

    rows = list(conn.execute(sa.text("SELECT id, template_key FROM plans")))
    for row in rows:
        template_key = row.template_key
        template_id: str | None = None
        template_version: int | None = None

        if isinstance(template_key, str) and "/v" in template_key:
            left, right = template_key.rsplit("/v", maxsplit=1)
            if left and right.isdigit():
                template_id = left
                template_version = int(right)

        if template_id is None or template_version is None:
            raise RuntimeError(
                f"Cannot backfill plan template fields for plan {row.id}: {template_key!r}"
            )

        conn.execute(
            sa.text(
                "UPDATE plans SET template_id = :template_id, template_version = :template_version WHERE id = :id"
            ),
            {
                "id": row.id,
                "template_id": template_id,
                "template_version": template_version,
            },
        )

    op.alter_column("plans", "template_id", nullable=False)
    op.alter_column("plans", "template_version", nullable=False)

    for template_id, version in (("birth_de", 1), ("birth_de", 2)):
        _, compiled_hash = _read_compiled_and_hash(template_id, version)
        conn.execute(
            sa.text(
                """
                INSERT INTO template_versions (
                    id, template_id, version, status, template_key,
                    published_at, compiled_hash, created_at, updated_at
                )
                VALUES (
                    :id, :template_id, :version, 'published', :template_key,
                    now(), :compiled_hash, now(), now()
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "template_id": template_id,
                "version": version,
                "template_key": _derive_key(template_id, version),
                "compiled_hash": compiled_hash,
            },
        )


def downgrade() -> None:
    op.drop_constraint("fk_plans_upgraded_from_plan_id", "plans", type_="foreignkey")
    op.drop_index("ix_plans_template_id", table_name="plans")
    op.drop_column("plans", "upgraded_from_plan_id")
    op.drop_column("plans", "template_version")
    op.drop_column("plans", "template_id")

    op.drop_index("ix_template_versions_template_id", table_name="template_versions")
    op.drop_table("template_versions")
