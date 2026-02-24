# Life‑Event Workflow Plattform – Projektaufbau & Schritt‑für‑Schritt Anleitung (für Codex)

Ziel dieses Dokuments: Eine **konkrete, ausführliche Bauanleitung** für eine skalierbare Web‑Plattform (später optional Mobile Apps), die Lebensereignisse (z. B. „Geburt“) als **personalisierte Workflows** abbildet.

Dieses Dokument ist so geschrieben, dass du es 1:1 an ein Coding‑Tool (z. B. Codex) geben kannst.

---

## 0) Grundprinzip (wichtig, bevor du loslegst)

Du baust **keine Content‑Website**, sondern eine **Engine**:

- **Workflow Template (versioniert)** = Wissen als Daten (Tasks, Abhängigkeiten, Deadlines, Regeln, Content)
- **Planner** = generiert aus Template + Facts einen personalisierten Plan
- **Runtime** = speichert Plan‑Snapshot, Task‑Status, Recompute, Reminder

Wichtigste Designregeln:
1) **Templates statt if/else im Code**
2) **Versionierung + Tests ab Tag 1**
3) **Snapshot pro Nutzerplan** (alte Pläne bleiben stabil, auch wenn Templates aktualisiert werden)
4) **Trennung**: Workflow (Graph) vs Entscheidungen (Eligibility) vs Content (Markdown)

---

## 1) Technologie‑Stack (EU‑freundlich, zukunftssicher)

### Frontend (Website + App)
- **Next.js (React, TypeScript)**
  - SEO für Event‑Landing Pages (`/events/*`)
  - eingeloggter App‑Bereich (`/app/*`)
- **PWA** (Phase 2): installierbar, Offline light, Push (später)

Warum Next.js?
- Maximale SEO‑Power (Growth‑Kanal #1)
- App‑artige UX möglich
- Später Mobile Apps möglich, weil die Business‑Logik im Backend steckt

### Backend
- **Python: FastAPI**
  - API‑first Architektur
  - passt zu Python‑Kompetenz
- **PostgreSQL**
  - stabil, Standard
  - JSONB für Facts / Template Snapshot / compiled_json
- **Redis + Celery**
  - Background Jobs (Reminder Emails, Recompute, wöchentliche Digest)

### Storage (Dokumente)
- **S3‑kompatibles Object Storage in der EU** (z. B. Hetzner, MinIO auf Hetzner)
- In DB nur Metadaten + Storage Keys

### CI/CD
- GitHub Actions (oder GitLab CI)
- `pytest` (Template Regression)
- Lint/Format: `ruff`, `black`, `mypy` (optional)
- Frontend: `eslint`, `prettier`

### EU Hosting (empfohlen)
- **Hetzner** (DE/EU): Backend + Worker + Postgres (managed oder self-hosted) + Storage
- Reverse Proxy: Caddy oder Nginx (TLS)

---

## 2) Repo‑Struktur (Monorepo)

```
life-event/
  backend/
    app/
      main.py
      api/
      core/
      db/
      domain/
      compiler/
      workers/
      tests/
    pyproject.toml
    Dockerfile
  frontend/
    package.json
    next.config.js
    app/ (Next App Router)
    public/
  workflows/
    birth_de/
      v1/
        compiled.json
        tests/
          tc_001.yaml
          tc_002.yaml
  infra/
    docker-compose.yml
    github-actions/
      ci.yml
  README.md
```

Warum Workflows im Repo?
- Änderungen sind **diffbar**, reviewbar, versionierbar
- Tests laufen in CI und verhindern, dass du “aus Versehen” Regeln brichst

---

## 3) Das Domain‑Modell (Engine‑Kern)

### 3.1 Facts (Nutzerprofil)
Facts sind Schlüssel‑Werte, die im Onboarding gesammelt werden.

Beispiele (Geburt):
- `state` (Bundesland)
- `birth_date`
- `married` (bool)
- `employment_type` (enum)
- `public_insurance` (bool) / `private_insurance` (bool)
- optional: `income_last_12m`, `single_parent`

Regel: **UI‑Fragen sind nur Mapper → Facts**
Die Engine arbeitet nur mit Facts.

### 3.2 Workflow Template (compiled_json)
Ein Template enthält:
- Graph: `nodes` + `edges` (DAG)
- Tasks: Deadline Regeln, Eligibility Regeln, Content, Links, Doks
- Recommendations: Optimierungs‑Cards (separat von Tasks)
- Template‑Version

**Stabile IDs** (z. B. `t_birth_certificate`) sind Pflicht.

### 3.3 Planner (Plan Generator)
Input:
- `compiled_json`
- `facts`

Output:
- Liste aktiver Tasks (Eligibility gefiltert)
- `due_date` berechnet (Deadline relativ zum Stichtag)
- `blocked_by` (nur aktive prerequisites)
- Empfehlungen (Cards)

### 3.4 Runtime (Plan‑Management)
- Plan Instanz speichert:
  - `template_id`, `template_version`
  - Snapshot
- Task Status: todo/done/dismissed
- Recompute bei Fact‑Änderungen (done bleibt done)
- Reminder Worker verschickt Emails/Push

---

## 4) Datenbank‑Schema (minimal, skalierbar)

### Tabellen (Vorschlag)

**templates**
- template_id (text)
- version (int)
- status (draft/published/deprecated)
- compiled_json (jsonb)
- created_at, published_at

**workflow_instances**
- instance_id (uuid)
- user_id (uuid)
- template_id (text)
- template_version (int)
- event_date (date)
- snapshot (jsonb)
- created_at

**task_instances**
- instance_id (uuid)
- task_id (text)
- status (todo/done/dismissed)
- due_date (date, nullable)
- completed_at (timestamp, nullable)
- notes (text, nullable)

**user_facts**
- user_id (uuid)
- facts (jsonb)
- updated_at

**recommendation_instances**
- instance_id (uuid)
- rec_id (text)
- status (open/applied/dismissed)
- created_at

**documents**
- document_id (uuid)
- user_id (uuid)
- instance_id (uuid, nullable)
- doc_type (text)
- storage_key (text)
- metadata (jsonb)
- created_at

**audit_log**
- id
- actor_id
- action
- payload (jsonb)
- created_at

---

## 5) API‑Design (Minimal, aber richtig)

Auth (MVP: Magic Link oder Email+PW):
- `POST /auth/login`
- `POST /auth/verify`
- `GET /me`

Facts:
- `PATCH /me/facts`
- `GET /me/facts`

Plans:
- `POST /plans`  (create plan from template + facts + event_date)
- `GET /plans/{id}`
- `POST /plans/{id}/recompute` (optional)

Tasks:
- `GET /plans/{id}/tasks`
- `PATCH /plans/{id}/tasks/{task_id}` (status, notes)

Recommendations:
- `GET /plans/{id}/recommendations`
- `PATCH /plans/{id}/recommendations/{rec_id}` (applied/dismissed)

Documents:
- `POST /documents/upload` (returns signed URL)
- `GET /documents`
- `GET /documents/{id}/download` (signed URL)
- `DELETE /documents/{id}`

---

## 6) Workflow erstellen (Detail‑Vorgehen)

Du erstellst Workflows nicht “im Code”, sondern als Template‑Dateien.

### Schritt 1 — Fact‑Dictionary definieren
Lege fest, welche Facts existieren und welche Werte sie annehmen können.

Beispiel:
- `employment_type`: employed | self_employed | mixed | unemployed | student

### Schritt 2 — Tasks definieren (flache Liste)
Für jede Task:
- `task_id` (stabil)
- `title`, `category`, `priority`
- `deadline` (offset zu `birth_date`)
- `docs_required`
- `links`
- `content`

### Schritt 3 — Abhängigkeiten definieren (edges)
Beispiel:
- `t_birth_certificate -> t_child_benefit`
- `t_birth_certificate -> t_parental_allowance`

### Schritt 4 — Eligibility Regeln (nur wo nötig)
Beispiel:
- PKV‑Task nur, wenn `private_insurance=true`

Regelformat (AST):
- `all / any / not` mit Predicates `{fact, op, value}`

### Schritt 5 — Recommendations definieren (separat)
Optimierungen als Cards:
- Eligibility
- Benefit Range
- Erklärung
- optional: “suggested task” oder Action Link

### Schritt 6 — Tests schreiben (Pflicht)
Testcases als YAML:
- Facts
- erwartete Task IDs (present/absent)
- erwartete Deadlines
- expected blocked_by
- Recommendations present/absent

### Schritt 7 — Publish (Version hochzählen)
Neue Version erzeugen:
- `birth_de v1` → `v2`
- CI muss grün sein (Regression)
- erst dann publishen

---

## 7) Engine‑Implementierung (Module & Responsibilities)

### backend/app/domain/
- `rules_ast.py`  (Rule Datenstruktur)
- `rules_eval.py` (Rule Auswertung)
- `deadlines.py`  (due_date Berechnung)
- `graph.py`      (toposort + cycle check + prerequisites)
- `planner.py`    (generate_plan: template + facts → plan)

### backend/app/compiler/
- Phase 1: nicht nötig (compiled.json direkt)
- Phase 2: `bpmn_parser.py`, `dmn_parser.py`, `compile_template.py`

### backend/app/workers/
- `celery_app.py`
- `jobs_reminders.py`
- `jobs_weekly_digest.py`

---

## 8) Schritt‑für‑Schritt Implementationsplan (MVP → skalierbar)

### Milestone 0 — Dev Setup (Tag 1)
1) Monorepo erstellen
2) Docker Compose: Postgres + Redis
3) FastAPI skeleton + health endpoint
4) Next.js skeleton
5) CI: Backend tests + Frontend build

**DoD**
- `docker compose up` läuft
- CI grün

---

### Milestone 1 — Template + Tests (Tag 2–4)
1) `workflows/birth_de/v1/compiled.json` erstellen (minimal)
2) 5–10 Testcases schreiben (`tc_001.yaml` etc.)
3) Validator + pytest runner

**DoD**
- Tests grün
- Graph validation + cycle check

---

### Milestone 2 — Planner Engine (Tag 5–8)
1) Rule evaluator
2) Deadline compute (relative_days)
3) Toposort ordering
4) generate_plan() Output definieren
5) Tests laufen lassen (Regression)

**Spec-Details (verbindlich)**
- Source of truth fuer Dependencies ist `graph.edges`.
- Unknown Dependency IDs sind Fehler; Dependencies auf inaktive Tasks werden gepruned.
- Fehlende Facts liefern bei allen Vergleichsoperatoren `False` (Ausnahme: `exists` prueft nur Key-Praesenz).

**DoD**
- `generate_plan()` deterministisch
- Testcases decken Varianten ab

---

### Milestone 3 — Backend Persistenz + API (Tag 9–13)
1) DB Modelle + Migration (alembic)
2) POST /plans:
   - facts speichern
   - template laden
   - planner ausführen
   - snapshot speichern
3) GET /plans/{id} + /tasks
4) PATCH task status
5) Recompute (optional)

**DoD**
- Plan erstellen & Tasks abhaken funktioniert end‑to‑end via API

---

### Milestone 4 — Frontend MVP (Tag 14–20)
1) Event Landing Page `/events/geburt`
2) Onboarding Formular (Facts)
3) Plan erstellen Call (POST /plans)
4) Taskliste anzeigen + abhaken
5) Dashboard minimal (Progress, nächste Fristen)

**DoD**
- Nutzer kann Plan erstellen und nutzen

---

### Milestone 5 — Reminder Worker (Tag 21–24)
1) Celery job: „Tasks due in next 3 days“
2) Email Provider integrieren
3) Templates für Emails

**DoD**
- Reminder Emails funktionieren zuverlässig

---

### Milestone 6 — Diagramm Authoring (später, aber geplant)
1) Modellierungsstandard festlegen: BPMN/DMN
2) Regeln für Metadaten in BPMN `extensionElements`
3) Compiler: BPMN/DMN → compiled_json
4) CI: compile + validate + tests

**DoD**
- Diagramm ist Source of Truth, compiled_json wird automatisch erzeugt

---

## 9) Frontend‑Seitenstruktur (SEO + App sauber getrennt)

- `/` Landing
- `/events/geburt` (SEO + CTA)
- `/app/onboarding` (Facts sammeln)
- `/app/plan/{id}` (Dashboard)
- `/app/plan/{id}/tasks` (Taskliste)
- `/app/documents` (später)

---

## 10) Später Mobile Apps deployen (ohne Rewrite)

Du erreichst App‑Fähigkeit, wenn:
- Businesslogik komplett im Backend ist
- Frontend nur Client ist
- API stabil ist

Dann kannst du später:
- React Native (Expo) App bauen
- gleichen API‑Client nutzen
- gleiche Templates/Engine weiterverwenden

---

## 11) Definition of Done (Projekt‑weit)

- Templates sind versioniert und werden in CI getestet
- Planner generiert deterministische Pläne
- User‑Instanzen sind Snapshots (keine ungewollten Änderungen bei Template Updates)
- End‑to‑End Flow: Event auswählen → Facts → Plan → Tasks abhaken → Reminder

---

## 12) Start‑Checkliste (was du JETZT als erstes machst)

1) Repo + Docker Compose
2) `compiled.json` für Geburt v1 (minimal)
3) 5 Testcases
4) Planner bauen und Tests grün
5) API endpoints `/plans` + `/tasks`
6) Next.js UI minimal

Wenn diese 6 Punkte stehen, hast du ein stabiles Fundament für “groß”.
