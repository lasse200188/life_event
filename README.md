# life-event

Monorepo for the Life Event workflow platform.

## Quickstart

### Infrastructure
```bash
cd infra
docker compose up -d
# Falls 5432/6379 bereits belegt sind:
POSTGRES_PORT=5433 REDIS_PORT=6380 docker compose up -d
```

### Backend
```bash
cd backend
pip install -e .[dev]
# optional: Postgres statt SQLite nutzen
export DATABASE_URL='postgresql+psycopg://life_event:life_event@localhost:5432/life_event'
# optional: bei Postgres auto create_all erzwingen (default: nur bei SQLite)
export AUTO_CREATE_SCHEMA=1
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
# optional: API URL (default: http://localhost:8000)
export NEXT_PUBLIC_API_BASE_URL='http://localhost:8000'
npm run dev
npm run build
```

### Browser/Backend CORS
```bash
# default allows localhost:3000 and 127.0.0.1:3000
export CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000'
```

## Milestone 3: Persisted Plans + Tasks API

### Endpoints
- `POST /plans`
  - Input: `template_key`, `facts`
  - Output: `201` with `id`, `links`, timestamps
- `GET /plans/{id}`
  - Query: `include_snapshot` (default `false`)
  - Returns plan shell + `snapshot_meta`, optional full `snapshot`
- `GET /plans/{id}/tasks`
  - Query: `status`, `include_metadata`
  - Returns stable order by `sort_key`
- `PATCH /plans/{plan_id}/tasks/{task_id}`
  - Input: `{ "status": "done|todo|...", "force": false }`
  - Idempotent updates; `completed_at` handled consistently
  - Blocked tasks require `force: true` (otherwise `409 TASK_BLOCKED`)
  - Decision-Tasks (`metadata.tags` contains `decision`) cannot be manually completed (`409 TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN`)
- `PATCH /plans/{plan_id}/facts`
  - Input: `{ "facts": {...}, "recompute": true|false }`
  - Merges facts and optionally recomputes plan/tasks
- `POST /plans/{plan_id}/recompute`
  - Rebuilds active tasks from current facts
  - Keeps already completed tasks as `done` by `task_key` when still active

## Milestone 4: Minimal nutzbares Produkt (Frontend)

### Implementierte Routen
- `/events/geburt`: statische SEO Landing Page mit CTA
- `/app/onboarding`: Facts erfassen und `POST /plans`
- `/app/plan/{id}`: Dashboard mit Fortschritt, Fristen, kritischen Tasks
- `/app/plan/{id}/tasks`: Taskliste, Sortierung, Status-Updates

### Frontend API usage (Backend as single source of truth)
- `POST /plans`
- `GET /plans/{id}`
- `GET /plans/{id}/tasks?include_metadata=true`
- `PATCH /plans/{id}/tasks/{task_id}`
- `PATCH /plans/{id}/facts`
- `POST /plans/{id}/recompute`

### Decision-Task UX (v2)
- Decision-Tasks are detected via `metadata.tags` containing `decision`.
- Decision-Tasks do not render the done-checkbox in the task list.
- User selections (e.g. child insurance GKV/PKV) require confirmation before facts patch + recompute.

### Facts-Mapping (Onboarding)
- Gesendet werden:
  - `birth_date`
  - `employment_type`
  - `married`
  - `public_insurance` (optional)
  - `private_insurance` (optional)
- Bei "Keine Angabe" werden Insurance-Flags nicht gesendet (statt `false`).

### Task-Metadata in API
Beim Persistieren werden `metadata` pro Task mitgeschrieben:
- `category`
- `priority`
- `tags`
- `ui_actions`
- `blocked_by`

Damit koennen Frontend-Ansichten u. a. `tags: ["critical"]` fuer "kritische Tasks" nutzen.

Zusätzlich liefert die Task-API ein explizites Feld `task_kind`:
- `normal`
- `decision`

`task_kind` wird serverseitig berechnet (`decision`, wenn `metadata.tags` `decision` enthält oder `metadata.ui_actions` gesetzt ist). Dadurch ist die UI von Template-Details entkoppelt.

### Error model
All domain errors use:
```json
{
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

Error code convention:
- `TEMPLATE_NOT_FOUND`
- `PLAN_NOT_FOUND`
- `TASK_NOT_FOUND`
- `TASK_BLOCKED`
- `TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN`
- `PLANNER_INPUT_INVALID`
- `PERSISTENCE_ERROR`

Status code convention:
- `422`: request schema/enum/type validation
- `404`: missing template/plan/task
- `400`: planner cannot process otherwise valid input

### Data model (persisted)
- `plans`: `template_key`, `facts`, `snapshot`, `status`, timestamps
- `tasks`: `plan_id`, `task_key`, `status`, `due_date`, `metadata`, `sort_key`, timestamps

## Database migrations (Alembic)

```bash
cd backend
# uses DATABASE_URL if set; otherwise alembic.ini default
alembic upgrade head
alembic downgrade -1
```

Initial migration is in:
- `backend/alembic/versions/20260224_01_init_plans_tasks.py`

## Workflow quality gates (Milestone 1+2)

### Validate all workflow templates
```bash
cd backend
python -m app.tools.validate_all_workflows ../workflows
```

### Run workflow regression tests only
```bash
cd backend
python -m pytest -q -m workflow
```

### Run non-workflow backend tests
```bash
cd backend
python -m pytest -q -m "not workflow"
```

### Run blocked task policy tests (Milestone 4+)
```bash
cd backend
python -m pytest -q app/tests/test_plans_api.py -k "blocked_task"
```

### Run full backend quality check (same order as CI)
```bash
cd backend
python -m app.tools.validate_all_workflows ../workflows
python -m pytest -q -m workflow
python -m pytest -q -m "not workflow"
ruff check .
black --check .
```

## Planner engine semantics (Milestone 2)

- `generate_plan(workflow, user_input)` is pure logic (no DB/IO/side effects).
- Dependency source of truth is `workflow.graph.edges`.
- Unknown dependency IDs in `graph.edges` are hard errors.
- Dependencies to inactive tasks are soft-pruned from output.
- Missing fact handling in rules:
  - `exists`: checks key presence.
  - all other operators evaluate to `False` when fact is missing.

## Repository layout (current)

- `workflows/<event>/<version>/compiled.json`: versioned workflow templates
- `workflows/<event>/<version>/tests/tc_*.yaml`: regression fixtures
- `backend/app/planner/`: planner engine
- `backend/app/api/`: FastAPI routes + schemas
- `backend/app/db/`: SQLAlchemy models + session
- `backend/app/services/`: template/plan/task services
- `backend/alembic/`: database migrations
- `backend/app/tests/test_plans_api.py`: API E2E tests for M3
