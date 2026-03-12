from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import TemplateVersion
from app.services.errors import ApiError
from app.services.template_repository import TemplateRepository

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_DEPRECATED = "deprecated"


class TemplateCatalogService:
    def __init__(self, template_repository: TemplateRepository | None = None) -> None:
        self.template_repository = template_repository or TemplateRepository()

    def list_templates(self, session: Session) -> list[dict[str, Any]]:
        rows = list(
            session.scalars(
                select(TemplateVersion).order_by(
                    TemplateVersion.template_id.asc(), TemplateVersion.version.asc()
                )
            ).all()
        )
        grouped: dict[str, list[TemplateVersion]] = {}
        for row in rows:
            grouped.setdefault(row.template_id, []).append(row)

        result: list[dict[str, Any]] = []
        for template_id, versions in grouped.items():
            latest_published_version = _latest_published_version(versions)
            result.append(
                {
                    "template_id": template_id,
                    "latest_published_version": latest_published_version,
                    "version_count": len(versions),
                }
            )
        return result

    def bootstrap_defaults(self, session: Session) -> None:
        defaults = (("birth_de", 1), ("birth_de", 2))
        now = datetime.now(UTC)
        changed = False
        for template_id, version in defaults:
            template_key = self.template_repository.derive_template_key(
                template_id, version
            )
            row = session.scalar(
                select(TemplateVersion).where(
                    TemplateVersion.template_key == template_key
                )
            )
            if row is not None:
                continue
            try:
                compiled_hash = self.template_repository.compiled_hash(
                    template_id, version
                )
            except ApiError:
                continue
            session.add(
                TemplateVersion(
                    template_id=template_id,
                    version=version,
                    status=STATUS_PUBLISHED,
                    template_key=template_key,
                    published_at=now,
                    compiled_hash=compiled_hash,
                )
            )
            changed = True
        if changed:
            session.commit()

    def list_versions(self, session: Session, template_id: str) -> list[dict[str, Any]]:
        rows = self._list_rows_for_template(session, template_id)
        if not rows:
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_id}' not found",
            )

        latest_published_version = _latest_published_version(rows)
        return [
            {
                "template_id": row.template_id,
                "version": row.version,
                "status": row.status,
                "template_key": row.template_key,
                "published_at": row.published_at,
                "deprecated_at": row.deprecated_at,
                "is_latest_published": (
                    latest_published_version is not None
                    and row.version == latest_published_version
                    and row.status == STATUS_PUBLISHED
                    and row.deprecated_at is None
                ),
            }
            for row in rows
        ]

    def publish(
        self, session: Session, *, template_id: str, version: int
    ) -> TemplateVersion:
        row = session.scalar(
            select(TemplateVersion)
            .where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.version == version,
            )
            .with_for_update()
        )
        if row is None:
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_id}/v{version}' not found",
            )

        if row.status == STATUS_PUBLISHED:
            return row

        if row.status != STATUS_DRAFT:
            raise ApiError(
                status_code=409,
                code="TEMPLATE_PUBLISH_INVALID_TRANSITION",
                message=(
                    f"Cannot publish template '{row.template_key}' from status '{row.status}'"
                ),
            )

        template = self.template_repository.load_by_id_version(template_id, version)
        if (
            template.get("template_id") != template_id
            or template.get("version") != version
        ):
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message=f"Template file mismatch for '{row.template_key}'",
            )

        now = datetime.now(UTC)
        row.status = STATUS_PUBLISHED
        row.published_at = now
        row.compiled_hash = self.template_repository.compiled_hash(template_id, version)
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def resolve_latest_published(
        self, session: Session, *, template_id: str
    ) -> TemplateVersion:
        latest = session.scalar(
            select(TemplateVersion)
            .where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.status == STATUS_PUBLISHED,
                TemplateVersion.deprecated_at.is_(None),
            )
            .order_by(TemplateVersion.version.desc())
            .limit(1)
        )
        if latest is not None:
            return latest

        exists = session.scalar(
            select(func.count())
            .select_from(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
        )
        if int(exists or 0) == 0:
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_id}' not found",
            )

        raise ApiError(
            status_code=409,
            code="NO_PUBLISHED_TEMPLATE",
            message=f"Template '{template_id}' has no published version",
        )

    def resolve_published_by_key(
        self, session: Session, *, template_key: str
    ) -> TemplateVersion:
        row = session.scalar(
            select(TemplateVersion).where(TemplateVersion.template_key == template_key)
        )
        if row is None:
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_key}' not found",
            )
        if row.status != STATUS_PUBLISHED or row.deprecated_at is not None:
            raise ApiError(
                status_code=409,
                code="NO_PUBLISHED_TEMPLATE",
                message=f"Template '{template_key}' is not published",
            )
        return row

    def get_latest_published_version(
        self, session: Session, *, template_id: str
    ) -> int | None:
        row = session.scalar(
            select(TemplateVersion.version)
            .where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.status == STATUS_PUBLISHED,
                TemplateVersion.deprecated_at.is_(None),
            )
            .order_by(TemplateVersion.version.desc())
            .limit(1)
        )
        return int(row) if isinstance(row, int) else None

    def _list_rows_for_template(
        self,
        session: Session,
        template_id: str,
    ) -> list[TemplateVersion]:
        return list(
            session.scalars(
                select(TemplateVersion)
                .where(TemplateVersion.template_id == template_id)
                .order_by(TemplateVersion.version.asc())
            ).all()
        )


def _latest_published_version(rows: list[TemplateVersion]) -> int | None:
    published_versions = [
        row.version
        for row in rows
        if row.status == STATUS_PUBLISHED and row.deprecated_at is None
    ]
    if not published_versions:
        return None
    return max(published_versions)
