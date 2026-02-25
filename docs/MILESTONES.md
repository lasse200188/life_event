# Milestones

Stand: 2026-02-25

## Uebersicht

| Milestone | Status | Schwerpunkt |
|---|---|---|
| M1 | abgeschlossen | Workflow-Template-Struktur + Regressionstest-Framework |
| M2 | abgeschlossen | Planner-Engine (Eligibility, Deadlines, DAG, deterministische Ausgabe) |
| M3 | abgeschlossen | Persistenz von Plaenen/Tasks + Plans/Tasks API |
| M4 | abgeschlossen | Frontend-MVP (Onboarding, Dashboard, Taskliste) |
| M5 | abgeschlossen | Decision-Task-Flow + Fact-Recompute + task_kind API-Semantik |

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

## Nicht-Ziele der bisherigen Milestones

- Vollstaendige Auth-/Account-Journeys
- Dokumenten-Upload mit produktiver Storage-Integration
- Reminder/Notification-Worker in Produktion
- Multi-Event-Portfolio ueber Geburt hinaus
