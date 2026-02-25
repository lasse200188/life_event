from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    NotificationProfileResponse,
    NotificationProfileUpsertRequest,
    NotificationUnsubscribeResponse,
)
from app.db.session import get_db_session
from app.services.notification_profile_service import NotificationProfileService
from app.services.plan_service import PlanService

router = APIRouter(tags=["notifications"])


@router.put(
    "/plans/{plan_id}/notification-profile",
    response_model=NotificationProfileResponse,
)
def upsert_notification_profile(
    plan_id: UUID,
    payload: NotificationProfileUpsertRequest,
    session: Session = Depends(get_db_session),
) -> NotificationProfileResponse:
    PlanService().get_plan(session, plan_id)

    service = NotificationProfileService()
    profile = service.upsert_profile(
        session,
        plan_id=plan_id,
        email=payload.email,
        email_consent=payload.email_consent,
        locale=payload.locale,
        timezone=payload.timezone,
        reminder_due_soon_enabled=payload.reminder_due_soon_enabled,
    )

    return NotificationProfileResponse(
        id=profile.id,
        plan_id=profile.plan_id,
        email=profile.email,
        email_consent=profile.email_consent,
        locale=profile.locale,
        timezone=profile.timezone,
        reminder_due_soon_enabled=profile.reminder_due_soon_enabled,
        max_reminders_per_day=profile.max_reminders_per_day,
        unsubscribed_at=profile.unsubscribed_at,
        sendable=service.is_sendable(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/notifications/unsubscribe",
    response_model=NotificationUnsubscribeResponse,
)
def unsubscribe_from_notifications(
    token: str = Query(..., min_length=10),
    session: Session = Depends(get_db_session),
) -> NotificationUnsubscribeResponse:
    NotificationProfileService().unsubscribe_by_token(session, token=token)
    return NotificationUnsubscribeResponse(ok=True)
