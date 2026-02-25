from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    NotificationFailureClass,
    NotificationOutbox,
    NotificationOutboxStatus,
)
from app.notifications.time_utils import (
    BERLIN_TZ,
    is_within_send_window,
    next_send_window_start,
)


class NotificationOutboxService:
    def enqueue_due_soon(
        self,
        session: Session,
        *,
        profile_id: UUID,
        dedupe_key_raw: str,
        payload: dict,
        now: datetime,
    ) -> tuple[NotificationOutbox | None, bool]:
        item = NotificationOutbox(
            profile_id=profile_id,
            channel="email",
            type="task_due_soon",
            dedupe_key_raw=dedupe_key_raw,
            payload=payload,
            status=NotificationOutboxStatus.pending.value,
            failure_class=None,
            next_attempt_at=now,
            attempt_count=0,
        )
        session.add(item)

        try:
            session.flush()
            return item, True
        except IntegrityError:
            session.rollback()
            return None, False

    def count_created_today(
        self,
        session: Session,
        *,
        profile_id: UUID,
        now: datetime,
    ) -> int:
        local_day = now.astimezone(BERLIN_TZ).date()
        start_local = datetime.combine(local_day, datetime.min.time(), tzinfo=BERLIN_TZ)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(UTC)
        end_utc = end_local.astimezone(UTC)

        stmt = select(func.count(NotificationOutbox.id)).where(
            NotificationOutbox.profile_id == profile_id,
            NotificationOutbox.created_at >= start_utc,
            NotificationOutbox.created_at < end_utc,
        )
        return int(session.scalar(stmt) or 0)

    def lock_pending_batch(
        self, session: Session, *, now: datetime, limit: int
    ) -> list[NotificationOutbox]:
        stmt = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == NotificationOutboxStatus.pending.value,
                NotificationOutbox.next_attempt_at <= now,
            )
            .order_by(NotificationOutbox.next_attempt_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list(session.scalars(stmt).all())

        for row in rows:
            row.status = NotificationOutboxStatus.sending.value
            row.updated_at = now
            session.add(row)

        session.commit()
        return rows

    def mark_sent(
        self,
        session: Session,
        *,
        outbox_id: UUID,
        provider_message_id: str | None,
        now: datetime,
    ) -> None:
        item = session.get(NotificationOutbox, outbox_id)
        if item is None:
            return
        item.status = NotificationOutboxStatus.sent.value
        item.failure_class = None
        item.provider_message_id = provider_message_id
        item.sent_at = now
        item.updated_at = now
        session.add(item)
        session.commit()

    def mark_failed_or_retry(
        self,
        session: Session,
        *,
        outbox_id: UUID,
        failure_class: str,
        error_code: str | None,
        error_message: str | None,
        now: datetime,
        max_attempts: int = 5,
    ) -> None:
        item = session.get(NotificationOutbox, outbox_id)
        if item is None:
            return

        item.attempt_count += 1
        item.failure_class = failure_class
        item.last_error_code = error_code
        item.last_error_message = (error_message or "")[:500]
        item.updated_at = now

        if failure_class == NotificationFailureClass.permanent.value:
            item.status = NotificationOutboxStatus.dead.value
            item.next_attempt_at = now
        elif item.attempt_count >= max_attempts:
            item.status = NotificationOutboxStatus.dead.value
            item.failure_class = NotificationFailureClass.permanent.value
            item.last_error_code = "retry_exhausted"
            item.next_attempt_at = now
        else:
            backoff_minutes = [1, 5, 15, 60, 180]
            idx = max(0, min(item.attempt_count - 1, len(backoff_minutes) - 1))
            delay_minutes = backoff_minutes[idx]
            jitter = random.uniform(0.9, 1.1)
            candidate = now + timedelta(minutes=delay_minutes * jitter)
            if not is_within_send_window(candidate):
                candidate = next_send_window_start(candidate)
            item.status = NotificationOutboxStatus.pending.value
            item.next_attempt_at = candidate

        session.add(item)
        session.commit()

    def recover_stuck_sending(self, session: Session, *, now: datetime) -> int:
        threshold = now - timedelta(minutes=15)
        stmt = select(NotificationOutbox).where(
            and_(
                NotificationOutbox.status == NotificationOutboxStatus.sending.value,
                NotificationOutbox.updated_at < threshold,
            )
        )
        recovered = 0
        for item in session.scalars(stmt).all():
            item.status = NotificationOutboxStatus.pending.value
            item.failure_class = NotificationFailureClass.retryable.value
            item.last_error_code = "stuck_sending_recovered"
            item.last_error_message = "Recovered stale sending item"
            item.next_attempt_at = next_send_window_start(now)
            item.updated_at = now
            session.add(item)
            recovered += 1

        if recovered:
            session.commit()
        return recovered
