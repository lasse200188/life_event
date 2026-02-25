from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.db.base import Base
from app.db.models import NotificationOutbox, Task, TaskStatus
from app.db.session import configure_engine, get_engine, get_session_factory
from app.main import app
from app.notifications.templates import render_task_due_soon
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


def test_scan_creates_outbox_for_due_tomorrow_and_is_idempotent(client: TestClient) -> None:
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
            session.scalars(select(Task).where(Task.plan_id == plan_id).order_by(Task.sort_key.asc())).all()
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
