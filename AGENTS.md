# AGENTS.md

## Local Environment Policy

- Prefer a project-local virtualenv at `.venv` managed with `uv`.
- Preferred bootstrap:
  - `uv venv --clear .venv`
  - `source .venv/bin/activate`
  - `uv pip install -e './backend[dev]'`

## Backend Test Commands

- Preferred:
  - `make setup`
  - `make test`
- `cd backend && python -m app.tools.validate_all_workflows ../workflows`
- `cd backend && python -m pytest -q -m workflow`
- `cd backend && python -m pytest -q -m "not workflow"`

## Collaboration Rule

- If a required system-level dependency/tool is missing (e.g. apt package, root-only install), explicitly ask the user to install it and continue afterward.
