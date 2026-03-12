# Release Notes

## 2026-03-12 - Milestone 7 abgeschlossen

### Highlights

- Recompute auf Merge-Strategie umgestellt (statt Full-Recreate).
- Ineligible Tasks werden jetzt soft-dismissed (`skipped`) statt geloescht.
- Reaktivierung bereits vorhandener Tasks bei erneuter Eligibility.
- Fact Evolution eingefuehrt: `migrate -> normalize -> planner`.
- `facts_hash` auf normalisierten Facts plus Fast-Path fuer no-op Fact-Changes.
- Recompute-Grund (`MANUAL|FACT_CHANGE|TEMPLATE_UPDATE`) in API/Snapshot.
- Snapshot-Deltas fuer Task-/Deadline-/Fact-Aenderungen.
- Neue Persistenzspalte `tasks.task_template_version` inkl. Alembic-Migration.

### API / Behaviour

- `POST /plans/{id}/recompute?reason=...` unterstuetzt Recompute-Reason.
- `PATCH /plans/{id}/facts` triggert Recompute intern mit `reason=FACT_CHANGE`.
- Snapshot (bei `include_snapshot=true`) enthaelt:
  - `facts_hash`
  - `template_version`
  - `fact_schema_version`
  - `recompute`
  - `recompute_delta`

### Test / Validation

- Lokale Tests und Linting erfolgreich:
  - `make test`
  - `make lint-backend`
- Alembic-Migration erfolgreich auf DB ausgefuehrt:
  - `alembic_version = 20260311_01`
