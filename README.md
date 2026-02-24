# life-event

Monorepo skeleton for the Life Event workflow platform.

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
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run build
```

## Workflow quality gates (Milestone 1)

### Validate all workflow templates
This validates all `workflows/**/compiled.json` files for JSON + graph semantics.

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
- Dependency source of truth is `workflow.graph.edges` (not task-local `depends_on` fields).
- Unknown dependency IDs in `graph.edges` are hard errors.
- Dependencies to inactive tasks are soft-pruned from output.
- Rule evaluation behavior for missing facts:
  - `exists`: checks key presence.
  - all other operators (`=`, `!=`, `in`, `>`, `>=`, `<`, `<=`): evaluate to `False` when the fact is missing.

## Current CI pipeline

`backend-tests` runs:
1. dependency install
2. validate all workflow templates
3. workflow tests (`-m workflow`)
4. remaining tests (`-m "not workflow"`)
5. lint (`ruff`)
6. format check (`black --check`)

`frontend-build` runs:
1. `npm install`
2. `npm run build`

## Repository layout (current)

- `workflows/<event>/<version>/compiled.json`: versioned workflow templates
- `workflows/<event>/<version>/tests/tc_*.yaml`: regression fixtures
- `backend/app/domain/workflow_validator.py`: graph validation + cycle detection
- `backend/app/tools/validate_all_workflows.py`: cross-workflow validator CLI
- `backend/app/tests/test_workflow_validation.py`: validator tests
- `backend/app/tests/test_workflow_regressions_all.py`: auto-discovered workflow regressions
