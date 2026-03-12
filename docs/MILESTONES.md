# Milestones

Stand: 2026-03-11

## Uebersicht

| Milestone | Status | Schwerpunkt |
|---|---|---|
| M1 | abgeschlossen | Workflow-Template-Struktur + Regressionstest-Framework |
| M2 | abgeschlossen | Planner-Engine (Eligibility, Deadlines, DAG, deterministische Ausgabe) |
| M3 | abgeschlossen | Persistenz von Plaenen/Tasks + Plans/Tasks API |
| M4 | abgeschlossen | Frontend-MVP (Onboarding, Dashboard, Taskliste) |
| M5 | abgeschlossen | Decision-Task-Flow + Fact-Recompute + task_kind API-Semantik |
| M6 | abgeschlossen | Reminder-Notifications (Celery + Outbox + Brevo + Templates) |
| M7 | abgeschlossen | Recompute 2.0 + Fact Evolution (Stabilitaet unter Realbedingungen) |
| M8 | geplant | Template Versioning in Production |
| M9 | geplant | Document Management strukturiert |
| M10 | geplant | Recommendation Engine 2.0 (Monetarisierungsvorbereitung) |
| M11 | geplant | Multi-Event Architektur |
| M12 | geplant | Growth Architektur (SEO + Funnel Engine) |

## Details

### M1 - Workflow-Contracts

Ziel:
- Wissen als Templates modellieren statt harter if/else-Logik
- Templates versionieren und regressionssicher machen

Umgesetzt:
- `workflows/<event>/<version>/compiled.json`
- Regressionstest-Rahmen fuer `tasks_present`, `tasks_absent`, `deadlines`, `blocked_initially`
- Validierung von Graph-Konsistenz und Zyklen

### M2 - Planner Engine

Ziel:
- Reine, deterministische Plan-Generierung aus `workflow + facts`

Umgesetzt:
- Eligibility-Auswertung (`all`, `any`, `not`, Pradikate)
- Deadline-Berechnung (`relative_days`)
- Topologische Sortierung fuer aktive Tasks
- Soft-Pruning von Dependencies auf inaktive Tasks

### M3 - Persisted Plans + Tasks API

Ziel:
- Plan-Ausgabe persistieren und ueber API abruf-/aenderbar machen

Umgesetzt:
- Tabellen fuer `plans` und `tasks`
- Endpunkte fuer Create/Get/List/Patch (Tasks)
- Snapshot-Metadaten in Plan-Antwort
- Einheitliches Error-Envelope-Format

### M4 - Frontend MVP

Ziel:
- End-to-End nutzbarer Flow im Browser

Umgesetzt:
- SEO-Landingpage `/events/geburt`
- Onboarding-Facts -> `POST /plans`
- Plan-Dashboard mit Fortschritt/Deadlines
- Taskliste mit Sorting, Blockierungsanzeige, Status-Update

### M5 - Decision-Tasks und Recompute

Ziel:
- Echte Entweder/Oder-Entscheidungen sauber modellieren

Umgesetzt:
- `birth_de/v2` mit Decision-Task fuer Kinder-Versicherung
- Fact-Normalisierung im Backend (`child_insurance_kind`)
- `PATCH /plans/{id}/facts` und `POST /plans/{id}/recompute`
- Done-Status bleibt bei Recompute erhalten (per `task_key`)
- Decision-Tasks sind nicht manuell auf `done` patchbar
- Frontend-Confirm vor Entscheidungs-Action
- Neues API-Feld `task_kind` (`normal|decision`) fuer UI-Entkopplung

### M6 - Reminder Notifications

Ziel:
- Zuverlaessige Deadline-Reminder mit Idempotenz und robustem Versand

Umgesetzt:
- Tabellen `notification_profiles` (Opt-in/Praeferenzen) und `notification_outbox` (Queue + Status)
- Periodische Celery-Jobs:
  - taeglicher Due-soon-Scan
  - regelmaessiger Outbox-Dispatch
- Due-soon-Logik in `Europe/Berlin` fuer Fenster `heute..heute+3`
- Dedupe pro Profil/Tag/Typ/Channel via `dedupe_key_raw` (unique)
- Outbox-Lifecycle `pending|sending|sent|dead` mit Retry-Backoff, Jitter, `stuck sending`-Recovery
- Brevo API Provider mit Fehlerklassifizierung (permanent vs retryable) und Dry-run/Whitelist fuer dev
- Template-Rendering fuer `task_due_soon` (Subject + Text + HTML, de-DE Datumsformat)
- Neue API-Endpunkte:
  - `PUT /plans/{id}/notification-profile`
  - `GET /notifications/unsubscribe?token=...`

### M7 - Recompute 2.0 + Fact Evolution (abgeschlossen)

Ziel:
- Engine robust gegen nachtraeglich geaenderte Facts
- Engine robust gegen neue Template-Versionen
- Engine robust gegen Feature-Erweiterungen

Warum jetzt:
- Snapshot-Logik vorhanden
- Recompute ist optional vorhanden
- Persistierte Task-Instanzen vorhanden
- Es fehlen saubere Evolutionsregeln fuer sichere Weiterentwicklung

Umgesetzt:
- Recompute als Merge statt Full-Recreate (`task_key`-basiert) mit Soft-Dismiss:
  - nicht mehr eligible -> `skipped`
  - wieder eligible -> Reaktivierung derselben Task-Instanz
  - `done` bleibt `done`
- Deadline-Policy hybrid:
  - offene Tasks werden neu berechnet
  - `done`/`skipped` bleiben stabil
- Snapshot erweitert um Evolutions-/Recompute-Transparenz:
  - `facts_hash` (auf migrierten + normalisierten Facts)
  - `template_version`, `fact_schema_version`
  - `recompute.reason` (`MANUAL|FACT_CHANGE|TEMPLATE_UPDATE`)
  - `recompute_delta` (added/soft_dismissed/reactivated/updated/status/deadline/facts_diff)
- Fast-Path fuer Fact-Only-Recompute:
  - Skip bei unveraendertem normalisiertem `facts_hash` (inkl. Template-/Engine-Version-Guard)
- Fact Evolution Pipeline eingefuehrt:
  - `migrate_to_latest_schema -> normalize_facts -> planner`
  - versionierte Migrationen im Service-Layer
- Persistenz erweitert:
  - `tasks.task_template_version` + Alembic Migration `20260311_01`
- API erweitert:
  - `POST /plans/{id}/recompute?reason=...`
- Regressionstests erweitert (Soft-Dismiss, Reactivation, Reason, Fast-Path)
- Lokal verifiziert:
  - `make test` und `make lint-backend` gruen
  - Alembic auf DB ausgefuehrt (`alembic_version=20260311_01`)

Definition of Done:
- Recompute ist deterministisch
- Kein Datenverlust bei Recompute/Migration
- Testcases decken Migrationsfaelle ab

### M8 - Template Versioning in Production (geplant)

Ziel:
- Mehrere Template-Versionen parallel betreiben

Ausgangslage:
- `template_id: "birth_de"` vorhanden
- `version: 1` im Compiled-Template vorhanden
- Es fehlt Lifecycle-Management

Geplant:
- Templates-API:
  - `GET /templates`
  - `GET /templates/{id}/versions`
- Publish-Flow:
  - `draft -> published`
  - Alte Version bleibt fuer bestehende Instanzen stabil
- Upgrade-Strategie:
  - optionaler "Upgrade Plan"-Button
  - erzeugt neue Instanz aus neuer Version
- CI-Regression:
  - v1-Tests bleiben gruener Standard
  - v2 darf v1 nicht kaputtmachen

Definition of Done:
- `birth_de` v1 und v2 parallel moeglich
- Alte Plaene bleiben stabil
- Upgrade erzeugt neue Snapshot-Instanz

### M9 - Document Management richtig machen (geplant)

Ziel:
- Dokumente sind strukturiert und nicht nur Upload

Ausgangslage:
- `docs_required` ist in Tasks vorhanden (Compiled)

Geplant:
- Dokument-Typ Registry:
  - `birth_certificate`
  - `id_card`
  - `income_proof`
  - `employer_form`
- Task -> Required Docs Status:
  - Dokument vorhanden?
  - Dokument fehlt?
  - optional vs. required
- UI:
  - Task zeigt fehlende Dokumente
  - Upload direkt aus Task moeglich
- Auto-Reminder:
  - Task done, aber Dokument fehlt

Definition of Done:
- Dokumente sind mit Tasks verknuepft
- System erkennt fehlende Unterlagen
- Reminder kann darauf reagieren

### M10 - Recommendation Engine 2.0 (Monetarisierungsvorbereitung) (geplant)

Ziel:
- Recommendations werden messbar, priorisierbar und monetarisierbar vorbereitet

Ausgangslage:
- `recommendations` ist im Compiled-Template bereits vorhanden

Geplant:
- Recommendation Scoring:
  - Impact Score (`benefit_estimate`)
  - Effort Score
  - Confidence Score
- Tracking:
  - `opened`
  - `applied`
  - `dismissed`
  - `ignored`
- Conversion Tracking:
  - `task_hint` -> wurde Task erledigt?
- Future-Ready:
  - `external_action` (Affiliate / Partner API)

Definition of Done:
- Recommendation-Lifecycle ist sauber modelliert
- Analytics ist moeglich
- Spaetere Monetarisierung ist vorbereitet

### M11 - Multi-Event Architektur (geplant)

Ziel:
- Mehrere Lebensereignisse parallel unterstuetzen

Beispiele:
- Umzug
- Heirat
- Scheidung
- Pflegefall
- Todesfall
- Selbststaendigkeit

Geplant:
- Event Registry:
  - `event_type`
  - `locale`
  - `active_templates`
- Dashboard:
  - mehrere aktive Plaene pro User
- Cross-Event Rules:
  - z. B. Heirat beeinflusst Geburt
  - gemeinsames Fact-Profil

Definition of Done:
- User kann mehrere Ereignisse starten
- Engine skaliert ohne Code-Aenderung pro neuem Event

### M12 - Growth Architektur (SEO + Funnel Engine) (geplant)

Ziel:
- SEO-Landingpages als strukturierte Onboarding-Funnels

Geplant:
- Event Landing Generator:
  - Template-Metadaten -> SEO-Seite
  - Structured Data
- Fact-Driven Funnel:
  - dynamische Fragen
  - conditional steps
- Save-before-login:
  - Pre-Plan ohne Account
  - spaeter claimen
- Tracking:
  - Step Dropoff
  - Completion Rate

Definition of Done:
- `/events/*` Seiten sind skalierbar
- Funnel ist optimierbar
- Analytics ist integriert

## Nicht-Ziele der bisherigen Milestones

- Vollstaendige Auth-/Account-Journeys
- Dokumenten-Upload mit produktiver Storage-Integration
- Multi-Event-Portfolio ueber Geburt hinaus
