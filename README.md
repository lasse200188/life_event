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
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run build
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
  - Input: `{ "status": "done|todo|..." }`
  - Idempotent updates; `completed_at` handled consistently

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
- `PLANNER_INPUT_INVALID`

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
