from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TemplateVersion
from app.services.template_repository import TemplateRepository


def seed_published_templates(
    session: Session,
    *,
    template_repository: TemplateRepository | None = None,
) -> None:
    repository = template_repository or TemplateRepository()
    now = datetime.now(UTC)

    for template_id, version in (("birth_de", 1), ("birth_de", 2)):
        template_key = repository.derive_template_key(template_id, version)
        existing = session.scalar(
            select(TemplateVersion).where(TemplateVersion.template_key == template_key)
        )
        if existing is not None:
            continue

        row = TemplateVersion(
            template_id=template_id,
            version=version,
            status="published",
            template_key=template_key,
            published_at=now,
            compiled_hash=repository.compiled_hash(template_id, version),
        )
        session.add(row)

    session.commit()
