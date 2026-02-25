from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.notifications.brevo_provider import BrevoEmailProvider
from app.notifications.config import NotificationConfig
from app.notifications.templates import render_task_due_soon
from app.notifications.time_utils import is_within_send_window
from app.services.notification_outbox_service import NotificationOutboxService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchSummary:
    picked: int
    sent: int
    retried: int
    dead: int
    recovered_stuck: int
    skipped_quiet_hours: int


class OutboxDispatcherService:
    def __init__(self, config: NotificationConfig) -> None:
        self.config = config
        self.outbox_service = NotificationOutboxService()
        self.provider = BrevoEmailProvider(config)

    def dispatch_pending(
        self, session: Session, *, now: datetime, batch_size: int = 100
    ) -> DispatchSummary:
        recovered_stuck = self.outbox_service.recover_stuck_sending(session, now=now)
        items = self.outbox_service.lock_pending_batch(
            session, now=now, limit=batch_size
        )

        picked = len(items)
        sent = 0
        retried = 0
        dead = 0
        skipped_quiet_hours = 0

        for item in items:
            payload = item.payload if isinstance(item.payload, dict) else {}
            to_email = payload.get("to_email")
            if not isinstance(to_email, str):
                to_email = ""

            if not is_within_send_window(now):
                self.outbox_service.reschedule_quiet_hours(
                    session,
                    outbox_id=item.id,
                    now=now,
                )
                skipped_quiet_hours += 1
                continue

            rendered = render_task_due_soon(payload)
            result = self.provider.send(to_email=to_email, rendered=rendered)

            if result.status == "sent":
                self.outbox_service.mark_sent(
                    session,
                    outbox_id=item.id,
                    provider_message_id=result.provider_message_id,
                    now=now,
                )
                sent += 1
            elif result.failure_class == "permanent":
                self.outbox_service.mark_failed_or_retry(
                    session,
                    outbox_id=item.id,
                    failure_class="permanent",
                    error_code=result.error_code,
                    error_message=result.error_message,
                    now=now,
                )
                dead += 1
            else:
                self.outbox_service.mark_failed_or_retry(
                    session,
                    outbox_id=item.id,
                    failure_class="retryable",
                    error_code=result.error_code,
                    error_message=result.error_message,
                    now=now,
                )
                retried += 1

        return DispatchSummary(
            picked=picked,
            sent=sent,
            retried=retried,
            dead=dead,
            recovered_stuck=recovered_stuck,
            skipped_quiet_hours=skipped_quiet_hours,
        )
