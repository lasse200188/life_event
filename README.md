# life-event

Monorepo fuer die Life-Event Workflow-Plattform.

Das Projekt kombiniert:
- eine regelbasierte Workflow-Engine (Templates + Planner)
- ein persistentes Plan/Task-Backend (FastAPI + SQLAlchemy)
- ein Next.js-Frontend fuer Onboarding, Plan-Dashboard und Taskbearbeitung

## Dokumentation

- Produkt-/Umsetzungsstand je Milestone: [docs/MILESTONES.md](docs/MILESTONES.md)
- API-Referenz (aktueller Stand): [docs/API.md](docs/API.md)
- Reminder/Scheduler Test-Guide: [docs/NOTIFICATIONS_TESTING.md](docs/NOTIFICATIONS_TESTING.md)
- Naechste geplante Arbeiten: [ROADMAP.md](ROADMAP.md)
- Langfristige Produktvision / Architekturleitfaden: [life_event_project_guide.md](life_event_project_guide.md)

## Aktueller Funktionsumfang

- Versionierte Workflows unter `workflows/<event>/<version>/compiled.json`
- Regressionstests pro Workflow unter `workflows/<event>/<version>/tests/tc_*.yaml`
- Planerzeugung aus Facts (`POST /plans`)
- Persistenz von Plaenen und Tasks inkl. Snapshot
- Task-Abhaengigkeiten, Blockierungslogik und Force-Override
- Decision-Task-Pattern (z. B. Kinder-Versicherung) mit Recompute
- Frontend-Routen:
  - `/events/geburt`
  - `/app/onboarding`
  - `/app/plan/{id}`
  - `/app/plan/{id}/tasks`

## Repository-Struktur

- `backend/`: FastAPI, Domain- und Service-Logik, DB-Modelle, Tests
- `frontend/`: Next.js App (SEO + App-UI)
- `workflows/`: versionierte Workflow-Templates + Regressionstests
- `infra/`: Docker Compose fuer lokale Basisdienste
- `docs/`: technische Projektdokumentation

## Quickstart

### 1) Infrastruktur

```bash
cd infra
docker compose up -d
# Falls 5432/6379 belegt sind:
POSTGRES_PORT=5433 REDIS_PORT=6380 docker compose up -d
```

### 2) Backend starten

```bash
cd backend
pip install -e .[dev]

# optional: Postgres nutzen
export DATABASE_URL='postgresql+psycopg://life_event:life_event@localhost:5432/life_event'

# optional: auto create_all auch bei Postgres erzwingen
export AUTO_CREATE_SCHEMA=1

uvicorn app.main:app --reload
```

Backend erreichbar unter `http://localhost:8000`.

### 3) Frontend starten

```bash
cd frontend
npm install

# optional, default ist http://localhost:8000
export NEXT_PUBLIC_API_BASE_URL='http://localhost:8000'

npm run dev
```

Frontend erreichbar unter `http://localhost:3000`.

### 4) CORS (optional)

```bash
# default erlaubt localhost:3000 und 127.0.0.1:3000
export CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000'
```

### 5) Reminder-Worker (Milestone Notifications)

```bash
cd backend

# Default: dry-run aktiv, damit keine echten Mails rausgehen
export EMAIL_DRY_RUN=true
export APP_BASE_URL='http://localhost:3000'
export EMAIL_FROM_ADDRESS='noreply@example.com'
export EMAIL_FROM_NAME='Life Event'
export CELERY_BROKER_URL='redis://localhost:6379/0'

# nur fuer echten Versand:
# export BREVO_API_KEY='...'
# optional whitelist fuer dev/staging
# export EMAIL_ALLOWED_RECIPIENT_DOMAINS='example.com,test.local'

celery -A app.worker.celery_app.celery_app worker --loglevel=info
celery -A app.worker.celery_app.celery_app beat --loglevel=info
```

Manueller Task-Trigger:
```bash
cd backend
celery -A app.worker.celery_app.celery_app call app.worker.tasks.reminder_scan_due_soon
celery -A app.worker.celery_app.celery_app call app.worker.tasks.dispatch_pending_outbox
```

## Qualitaetschecks

### Backend

```bash
cd backend
python -m app.tools.validate_all_workflows ../workflows
python -m pytest -q -m workflow
python -m pytest -q -m "not workflow"
ruff check .
black --check .
```

### Frontend

```bash
cd frontend
eslint .
prettier --check .
```

### Workflow-Datei schnell validieren

```bash
python -m json.tool workflows/birth_de/v2/compiled.json > /dev/null
```

## Hinweise zur Workflow-Entwicklung

- Bestehende Versionen nicht still ueberschreiben (`v1` bleibt stabil), stattdessen neue Version (`v2`, `v3`, ...)
- Jede Regel-/Eligibility-Aenderung braucht passende Regressionstests
- Decision-Logik nicht im Frontend verstecken: Facts serverseitig normalisieren und Plan neu berechnen
