# Notifications & Scheduler Testing

Diese Anleitung zeigt, wie du Reminder-Scan und Scheduler lokal testen kannst.

## Voraussetzungen

1. Infrastruktur starten:
```bash
cd infra
docker compose up -d
```

2. Backend-Dependencies installieren:
```bash
cd backend
pip install -e .[dev]
```

3. Datenbank-Migrationen anwenden:
```bash
cd backend
alembic upgrade head
```

## Relevante ENV-Variablen (lokal)

```bash
export DATABASE_URL='postgresql+psycopg://life_event:life_event@localhost:5432/life_event'
export CELERY_BROKER_URL='redis://localhost:6379/0'
export CELERY_RESULT_BACKEND='redis://localhost:6379/0'
export APP_BASE_URL='http://localhost:3000'

# sichere Defaults fuer lokale Tests
export EMAIL_DRY_RUN=true
export EMAIL_FROM_ADDRESS='noreply@example.com'
export EMAIL_FROM_NAME='Life Event'

# optional (wenn gesetzt, nur diese Domains erlaubt)
# export EMAIL_ALLOWED_RECIPIENT_DOMAINS='example.com'

# optional fuer stabile Token-Signatur
# export NOTIFICATION_TOKEN_SECRET='local-dev-secret'
```

## Test A: End-to-End mit manuellem Task-Trigger

1. API starten:
```bash
cd backend
uvicorn app.main:app --reload
```

2. Worker starten (separates Terminal):
```bash
cd backend
celery -A app.worker.celery_app.celery_app worker --loglevel=info
```

3. Plan erzeugen:
```bash
curl -sS -X POST http://localhost:8000/plans \
  -H 'content-type: application/json' \
  -d '{
    "template_key":"birth_de/v1",
    "facts":{"birth_date":"2026-04-01","employment_type":"employed","public_insurance":true,"private_insurance":false}
  }'
```
`id` aus der Antwort als `PLAN_ID` notieren.

4. Notification-Profile setzen:
```bash
curl -sS -X PUT http://localhost:8000/plans/$PLAN_ID/notification-profile \
  -H 'content-type: application/json' \
  -d '{
    "email":"user@example.com",
    "email_consent":true,
    "locale":"de-DE",
    "timezone":"Europe/Berlin",
    "reminder_due_soon_enabled":true
  }'
```

5. (Optional fuer reproduzierbaren Test) eine Task auf due-soon setzen:
```bash
cd backend
python3 - <<'PY'
import os
from datetime import date, timedelta
from uuid import UUID
from sqlalchemy import select
from app.db.session import configure_engine, get_session_factory
from app.db.models import Task, TaskStatus

plan_id = UUID(os.environ["PLAN_ID"])
configure_engine(os.environ.get("DATABASE_URL", "sqlite:///./life_event.db"))
with get_session_factory()() as s:
    task = s.scalars(select(Task).where(Task.plan_id == plan_id).order_by(Task.sort_key.asc())).first()
    task.status = TaskStatus.todo.value
    task.due_date = date.today() + timedelta(days=1)
    s.add(task)
    s.commit()
print("task updated")
PY
```

6. Reminder-Scan manuell triggern:
```bash
cd backend
celery -A app.worker.celery_app.celery_app call app.worker.tasks.reminder_scan_due_soon
```

7. Dispatch manuell triggern:
```bash
cd backend
celery -A app.worker.celery_app.celery_app call app.worker.tasks.dispatch_pending_outbox
```

8. Ergebnis in DB prüfen:
```bash
cd backend
python3 - <<'PY'
from sqlalchemy import select
from app.db.session import configure_engine, get_session_factory
from app.db.models import NotificationOutbox
import os

configure_engine(os.environ.get("DATABASE_URL", "sqlite:///./life_event.db"))
with get_session_factory()() as s:
    rows = s.scalars(select(NotificationOutbox).order_by(NotificationOutbox.created_at.desc())).all()
    for r in rows[:10]:
        print(r.id, r.status, r.attempt_count, r.last_error_code, r.provider_message_id, r.sent_at)
PY
```

Bei `EMAIL_DRY_RUN=true` sollte der Dispatch auf `sent` gehen, ohne echte Mail zu schicken.

## Test B: Scheduler (Beat) testen

1. Worker laufen lassen.
2. Beat starten (separates Terminal):
```bash
cd backend
celery -A app.worker.celery_app.celery_app beat --loglevel=info
```
3. Beobachte Logs:
- `reminder_scan_due_soon_summary`
- `dispatch_pending_outbox_summary`

## Erwartete Logik beim Test

- Due-soon Fenster: `today..today+3` in `Europe/Berlin`.
- Quiet Hours (`08:00..20:00` Berlin): außerhalb wird auf `pending` rescheduled (`QUIET_HOURS_DELAY`), ohne Attempt-Counter zu erhöhen.
- Daily cap basiert auf gesendeten Remindern (`sent`) pro Profil/Tag.
- Unsubscribe-Token bleibt stabil, bis gezielte Rotation durchgeführt wird.
