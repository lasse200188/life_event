from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import TemplateSummaryResponse, TemplateVersionResponse
from app.db.session import get_db_session
from app.services.template_catalog_service import TemplateCatalogService

router = APIRouter(tags=["templates"])


@router.get("/templates", response_model=list[TemplateSummaryResponse])
def list_templates(
    session: Session = Depends(get_db_session),
) -> list[TemplateSummaryResponse]:
    rows = TemplateCatalogService().list_templates(session)
    return [TemplateSummaryResponse(**row) for row in rows]


@router.get(
    "/templates/{template_id}/versions",
    response_model=list[TemplateVersionResponse],
)
def list_template_versions(
    template_id: str,
    session: Session = Depends(get_db_session),
) -> list[TemplateVersionResponse]:
    rows = TemplateCatalogService().list_versions(session, template_id)
    return [TemplateVersionResponse(**row) for row in rows]


@router.post(
    "/templates/{template_id}/versions/{version}/publish",
    response_model=TemplateVersionResponse,
)
def publish_template_version(
    template_id: str,
    version: int,
    session: Session = Depends(get_db_session),
) -> TemplateVersionResponse:
    row = TemplateCatalogService().publish(
        session,
        template_id=template_id,
        version=version,
    )
    latest_published_version = TemplateCatalogService().get_latest_published_version(
        session, template_id=template_id
    )
    return TemplateVersionResponse(
        template_id=row.template_id,
        version=row.version,
        status=row.status,
        template_key=row.template_key,
        published_at=row.published_at,
        deprecated_at=row.deprecated_at,
        is_latest_published=(
            isinstance(latest_published_version, int)
            and row.version == latest_published_version
            and row.status == "published"
            and row.deprecated_at is None
        ),
    )
