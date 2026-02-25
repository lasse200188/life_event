from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "life_event_worker",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "app.worker.tasks.reminders",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Berlin",
    enable_utc=True,
    beat_schedule={
        "reminder-scan-due-soon-daily": {
            "task": "app.worker.tasks.reminder_scan_due_soon",
            "schedule": crontab(minute=5, hour=8),
        },
        "dispatch-pending-outbox": {
            "task": "app.worker.tasks.dispatch_pending_outbox",
            "schedule": crontab(minute="*/5"),
        },
    },
)
