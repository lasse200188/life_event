from __future__ import annotations

import logging

from app.db.session import get_session_factory
from app.notifications.config import load_notification_config
from app.notifications.time_utils import now_berlin
from app.services.outbox_dispatcher_service import OutboxDispatcherService
from app.services.reminder_scanner_service import ReminderScannerService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.reminder_scan_due_soon")
def reminder_scan_due_soon() -> dict[str, int]:
    session_factory = get_session_factory()
    config = load_notification_config()
    now = now_berlin()

    with session_factory() as session:
        summary = ReminderScannerService().scan_due_soon(
            session,
            now=now,
            app_base_url=config.app_base_url,
        )

    payload = {
        "profiles_scanned": summary.profiles_scanned,
        "tasks_matched": summary.tasks_matched,
        "outbox_created": summary.outbox_created,
        "skipped_not_sendable": summary.skipped_not_sendable,
        "skipped_daily_cap": summary.skipped_daily_cap,
        "errors": summary.errors,
    }
    logger.info("reminder_scan_due_soon_summary", extra=payload)
    return payload


@celery_app.task(name="app.worker.tasks.dispatch_pending_outbox")
def dispatch_pending_outbox(batch_size: int = 100) -> dict[str, int]:
    session_factory = get_session_factory()
    config = load_notification_config()
    now = now_berlin()

    with session_factory() as session:
        summary = OutboxDispatcherService(config).dispatch_pending(
            session,
            now=now,
            batch_size=batch_size,
        )

    payload = {
        "picked": summary.picked,
        "sent": summary.sent,
        "retried": summary.retried,
        "dead": summary.dead,
        "recovered_stuck": summary.recovered_stuck,
        "skipped_quiet_hours": summary.skipped_quiet_hours,
    }
    logger.info("dispatch_pending_outbox_summary", extra=payload)
    return payload
