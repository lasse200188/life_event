# Repository Guidelines

## Projektstruktur & Modulaufbau
Die Zielarchitektur ist ein Monorepo mit klarer Trennung zwischen Engine, UI und Workflow-Daten:

- `backend/app/`: FastAPI, Domain-Logik (`rules_eval`, `deadlines`, `graph`, `planner`), API, Worker.
- `frontend/`: Next.js (SEO-Seiten unter `/events/*`, App-Bereich unter `/app/*`).
- `workflows/<event>/<version>/`: versionierte Templates (`compiled.json`) und Regressionstests (`tests/tc_*.yaml`).
- `infra/`: Docker Compose, CI-Definitionen.

Aktuell liegen erste Artefakte unter `birth_de_v1_templates_and_tests/...`. Neue Änderungen an Workflows immer versioniert (z. B. `v1` -> `v2`) statt bestehende Versionen still umzuschreiben.

## Build-, Test- und Dev-Kommandos
Nutze lokal und in CI reproduzierbare Checks:

- `docker compose up` startet Basisdienste (Postgres, Redis) für den MVP.
- `pytest` führt Backend- und Template-Regressionen aus.
- `ruff check . && black --check .` validiert Python-Qualität.
- `eslint . && prettier --check .` validiert Frontend-Qualität.
- `python -m json.tool workflows/birth_de/v1/compiled.json > /dev/null` prüft Template-JSON.

Solange einzelne Teile noch nicht eingecheckt sind, mindestens JSON/YAML-Syntax und Fixture-Konsistenz prüfen.

## Coding Style & Naming Conventions
- Python: PEP 8, 4 Spaces, Typannotationen in Kernmodulen (`planner`, `rules_eval`).
- TypeScript/React: ESLint + Prettier, Komponenten in PascalCase, Funktionen/Variablen in camelCase.
- Workflow-IDs sind stabil und snake_case: Tasks `t_*`, Recommendations `r_*`, Facts klar benannt (`employment_type`, `birth_date`).
- Testcases folgen `tc_###_<scenario>.yaml` (z. B. `tc_006_unmarried_student_gkv.yaml`).

## Testing Guidelines
Templates sind produktionskritisch und werden als Verträge getestet:

- Jede Regeländerung braucht Regressionstests für `tasks_present`, `tasks_absent`, `deadlines`, `blocked_initially`.
- Planner muss deterministisch bleiben (gleicher Input -> gleicher Plan).
- CI muss grün sein, bevor ein Template veröffentlicht wird.

## Commit- & PR-Richtlinien
- Conventional Commits nutzen, z. B. `feat(planner): add relative_days grace handling`.
- PRs enthalten:
  - fachliche Auswirkung (welche Nutzerfälle ändern sich),
  - betroffene Template-Version (`birth_de/v1` Patch oder neues `v2`),
  - Testnachweis (pytest/linters + relevante Fixture-Ergebnisse),
  - bei UI-Änderungen Screenshots für `/events/*` oder `/app/*`.

## Architekturprinzipien
- Templates statt harter `if/else`-Logik im Produktcode.
- Snapshot pro Workflow-Instanz, damit alte Nutzerpläne stabil bleiben.
- Strikte Trennung: Workflow-Graph, Eligibility-Regeln und Content.
