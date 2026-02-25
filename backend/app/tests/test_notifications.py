from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.db.base import Base
from app.db.models import NotificationOutbox, NotificationProfile, Task, TaskStatus
from app.db.session import configure_engine, get_engine, get_session_factory
from app.main import app
from app.notifications.config import NotificationConfig
from app.notifications.templates import render_task_due_soon
from app.services.outbox_dispatcher_service import OutboxDispatcherService
from app.services.reminder_scanner_service import ReminderScannerService

BERLIN_TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'test_notifications.db'}"
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_plan(client: TestClient) -> UUID:
    response = client.post(
        "/plans",
        json={
            "template_key": "birth_de/v1",
            "facts": {
                "birth_date": "2026-04-01",
                "employment_type": "employed",
                "public_insurance": True,
                "private_insurance": False,
            },
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _configure_profile(client: TestClient, plan_id: UUID) -> None:
    response = client.put(
        f"/plans/{plan_id}/notification-profile",
        json={
            "email": "user@example.com",
            "email_consent": True,
            "locale": "de-DE",
            "timezone": "Europe/Berlin",
            "reminder_due_soon_enabled": True,
        },
    )
    assert response.status_code == 200


def test_scan_creates_outbox_for_due_tomorrow_and_is_idempotent(
    client: TestClient,
) -> None:
    plan_id = _create_plan(client)
    _configure_profile(client, plan_id)

    session_factory = get_session_factory()
    now = datetime(2026, 2, 25, 8, 5, tzinfo=BERLIN_TZ)

    with session_factory() as session:
        first_task = session.scalar(
            select(Task).where(Task.plan_id == plan_id).order_by(Task.sort_key.asc())
        )
        assert first_task is not None
        first_task.status = TaskStatus.todo.value
        first_task.due_date = date(2026, 2, 26)
        session.add(first_task)
        session.commit()

    with session_factory() as session:
        summary = ReminderScannerService().scan_due_soon(
            session,
            now=now,
            app_base_url="http://localhost:3000",
        )
        assert summary.outbox_created == 1

    with session_factory() as session:
        summary = ReminderScannerService().scan_due_soon(
            session,
            now=now,
            app_base_url="http://localhost:3000",
        )
        assert summary.outbox_created == 0

        rows = list(session.scalars(select(NotificationOutbox)).all())
        assert len(rows) == 1


def test_scan_ignores_done_and_null_due_date(client: TestClient) -> None:
    plan_id = _create_plan(client)
    _configure_profile(client, plan_id)
    session_factory = get_session_factory()

    with session_factory() as session:
        tasks = list(
            session.scalars(
                select(Task)
                .where(Task.plan_id == plan_id)
                .order_by(Task.sort_key.asc())
            ).all()
        )
        assert len(tasks) >= 2
        tasks[0].status = TaskStatus.done.value
        tasks[0].due_date = date(2026, 2, 26)
        tasks[1].status = TaskStatus.todo.value
        tasks[1].due_date = None
        for task in tasks[:2]:
            session.add(task)
        session.commit()

    with session_factory() as session:
        summary = ReminderScannerService().scan_due_soon(
            session,
            now=datetime(2026, 2, 25, 8, 5, tzinfo=BERLIN_TZ),
            app_base_url="http://localhost:3000",
        )
        assert summary.outbox_created == 0
        assert summary.errors == 0


def test_due_soon_template_is_deterministic() -> None:
    payload = {
        "user_display_name": "Jens",
        "tasks": [
            {
                "title": "Geburtsurkunde beantragen",
                "due_date": "2026-02-26",
                "due_in_days": 1,
            },
            {
                "title": "Elterngeld beantragen",
                "due_date": "2026-02-28",
                "due_in_days": 3,
            },
        ],
        "plan_url": "http://localhost:3000/app/plan/123",
        "settings_url": "http://localhost:3000/notifications/manage?profile=1",
        "unsubscribe_url": "http://localhost:3000/notifications/unsubscribe?token=abc",
    }

    first = render_task_due_soon(payload)
    second = render_task_due_soon(payload)

    assert first.subject == second.subject
    assert first.text_body == second.text_body
    assert first.html_body == second.html_body
    assert "Geburtsurkunde beantragen" in first.text_body


def test_unsubscribe_token_is_stable_across_runs(client: TestClient) -> None:
    plan_id = _create_plan(client)
    _configure_profile(client, plan_id)
    session_factory = get_session_factory()

    with session_factory() as session:
        first_task = session.scalar(
            select(Task).where(Task.plan_id == plan_id).order_by(Task.sort_key.asc())
        )
        assert first_task is not None
        first_task.status = TaskStatus.todo.value
        first_task.due_date = date(2026, 2, 26)
        session.add(first_task)
        session.commit()

    with session_factory() as session:
        ReminderScannerService().scan_due_soon(
            session,
            now=datetime(2026, 2, 25, 8, 5, tzinfo=BERLIN_TZ),
            app_base_url="http://localhost:3000",
        )
        first_item = session.scalar(
            select(NotificationOutbox).order_by(NotificationOutbox.created_at.asc())
        )
        assert first_item is not None
        first_url = first_item.payload.get("unsubscribe_url")
        assert isinstance(first_url, str)
        first_token = first_url.split("token=")[-1]

        first_item.status = "sent"
        first_item.sent_at = datetime(2026, 2, 25, 9, 0, tzinfo=BERLIN_TZ)
        session.add(first_item)
        session.commit()

    with session_factory() as session:
        ReminderScannerService().scan_due_soon(
            session,
            now=datetime(2026, 2, 26, 8, 5, tzinfo=BERLIN_TZ),
            app_base_url="http://localhost:3000",
        )
        items = list(
            session.scalars(
                select(NotificationOutbox).order_by(NotificationOutbox.created_at.asc())
            ).all()
        )
        assert len(items) == 2
        second_url = items[1].payload.get("unsubscribe_url")
        assert isinstance(second_url, str)
        second_token = second_url.split("token=")[-1]
        assert second_token == first_token


def test_quiet_hours_reschedule_does_not_increment_attempts(
    client: TestClient,
) -> None:
    plan_id = _create_plan(client)
    _configure_profile(client, plan_id)
    session_factory = get_session_factory()

    with session_factory() as session:
        profile = session.scalar(
            select(NotificationProfile).where(NotificationProfile.plan_id == plan_id)
        )
        assert profile is not None
        outbox = NotificationOutbox(
            profile_id=profile.id,
            channel="email",
            type="task_due_soon",
            dedupe_key_raw="task_due_soon|email|profile:test|2026-02-25",
            payload={"to_email": "user@example.com", "tasks": []},
            status="pending",
            next_attempt_at=datetime(2026, 2, 25, 6, 0, tzinfo=BERLIN_TZ),
            attempt_count=0,
        )
        session.add(outbox)
        session.commit()

    config = NotificationConfig(
        app_base_url="http://localhost:3000",
        from_email="noreply@example.com",
        from_name="Life Event",
        brevo_api_key="",
        brevo_base_url="https://api.brevo.com/v3",
        email_dry_run=True,
        allowed_recipient_domains=set(),
    )
    with session_factory() as session:
        summary = OutboxDispatcherService(config).dispatch_pending(
            session,
            now=datetime(2026, 2, 25, 22, 30, tzinfo=BERLIN_TZ),
            batch_size=10,
        )
        assert summary.skipped_quiet_hours == 1

    with session_factory() as session:
        updated = session.scalar(select(NotificationOutbox))
        assert updated is not None
        assert updated.status == "pending"
        assert updated.attempt_count == 0
        assert updated.last_error_code == "QUIET_HOURS"


def test_consent_false_does_not_mark_unsubscribed(client: TestClient) -> None:
    plan_id = _create_plan(client)
    response = client.put(
        f"/plans/{plan_id}/notification-profile",
        json={
            "email": "user@example.com",
            "email_consent": False,
            "locale": "de-DE",
            "timezone": "Europe/Berlin",
            "reminder_due_soon_enabled": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sendable"] is False
    assert body["unsubscribed_at"] is None
