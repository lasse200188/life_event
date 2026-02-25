from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NotificationProfile, Task, TaskStatus
from app.notifications.dedupe import build_due_soon_dedupe_key_raw
from app.notifications.time_utils import BERLIN_TZ
from app.services.notification_outbox_service import NotificationOutboxService
from app.services.notification_profile_service import NotificationProfileService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanSummary:
    profiles_scanned: int
    tasks_matched: int
    outbox_created: int
    skipped_not_sendable: int
    skipped_daily_cap: int
    errors: int


class ReminderScannerService:
    def __init__(self) -> None:
        self.profile_service = NotificationProfileService()
        self.outbox_service = NotificationOutboxService()

    def scan_due_soon(
        self, session: Session, *, now: datetime, app_base_url: str
    ) -> ScanSummary:
        local_today = now.astimezone(BERLIN_TZ).date()
        local_end = local_today + timedelta(days=3)

        profiles = list(session.scalars(select(NotificationProfile)).all())

        profiles_scanned = 0
        tasks_matched = 0
        outbox_created = 0
        skipped_not_sendable = 0
        skipped_daily_cap = 0
        errors = 0

        for profile in profiles:
            profiles_scanned += 1
            try:
                if not self.profile_service.is_sendable(profile):
                    skipped_not_sendable += 1
                    continue

                sent_today = self.outbox_service.count_created_today(
                    session,
                    profile_id=profile.id,
                    now=now,
                )
                if sent_today >= profile.max_reminders_per_day:
                    skipped_daily_cap += 1
                    continue

                tasks = list(
                    session.scalars(
                        select(Task)
                        .where(Task.plan_id == profile.plan_id)
                        .where(Task.status == TaskStatus.todo.value)
                        .where(Task.due_date.is_not(None))
                        .where(Task.due_date >= local_today)
                        .where(Task.due_date <= local_end)
                        .order_by(Task.due_date.asc(), Task.sort_key.asc())
                    ).all()
                )

                if not tasks:
                    continue

                tasks_matched += len(tasks)

                unsubscribe_token = self.profile_service.issue_unsubscribe_token(
                    session,
                    profile=profile,
                )
                dedupe_key = build_due_soon_dedupe_key_raw(
                    profile_id=profile.id,
                    local_day=local_today,
                )

                payload_tasks = []
                for task in tasks:
                    if task.due_date is None:
                        continue
                    payload_tasks.append(
                        {
                            "task_key": task.task_key,
                            "task_instance_id": str(task.id),
                            "title": task.title,
                            "due_date": task.due_date.isoformat(),
                            "due_in_days": (task.due_date - local_today).days,
                            "category": (
                                task.metadata_json.get("category")
                                if isinstance(task.metadata_json, dict)
                                else None
                            ),
                            "priority": (
                                task.metadata_json.get("priority")
                                if isinstance(task.metadata_json, dict)
                                else None
                            ),
                        }
                    )

                if not payload_tasks:
                    continue

                payload = {
                    "profile_id": str(profile.id),
                    "plan_id": str(profile.plan_id),
                    "to_email": profile.email,
                    "locale": profile.locale,
                    "timezone": profile.timezone,
                    "tasks": payload_tasks,
                    "user_display_name": None,
                    "plan_url": f"{app_base_url}/app/plan/{profile.plan_id}",
                    "settings_url": (
                        f"{app_base_url}/notifications/unsubscribe?token={unsubscribe_token}"
                    ),
                    "unsubscribe_url": (
                        f"{app_base_url}/notifications/unsubscribe?token={unsubscribe_token}"
                    ),
                }

                _, created = self.outbox_service.enqueue_due_soon(
                    session,
                    profile_id=profile.id,
                    dedupe_key_raw=dedupe_key,
                    payload=payload,
                    now=now,
                )
                if created:
                    session.commit()
                    outbox_created += 1
            except Exception:
                session.rollback()
                errors += 1
                logger.exception(
                    "reminder_scan_profile_failed",
                    extra={"profile_id": str(profile.id)},
                )

        return ScanSummary(
            profiles_scanned=profiles_scanned,
            tasks_matched=tasks_matched,
            outbox_created=outbox_created,
            skipped_not_sendable=skipped_not_sendable,
            skipped_daily_cap=skipped_daily_cap,
            errors=errors,
        )
