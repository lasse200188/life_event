# Roadmap (Next)

Dieses Dokument beschreibt die naechsten groesseren Schritte nach den bereits abgeschlossenen Milestones M1-M5.

Fuer den bereits erreichten Stand siehe [docs/MILESTONES.md](docs/MILESTONES.md).

## Prioritaet A - Produktreife Kernfluss

1. Authentifizierung und Benutzerkontext
- Login/Session (z. B. Magic Link)
- Trennung von Plans pro User
- Zugriffsschutz fuer Plan-Endpunkte

2. Recompute-Transparenz
- Sichtbare Historie von Facts-Aenderungen
- Nachvollziehbarkeit, welche Tasks durch Recompute hinzugekommen/entfallen sind

3. Decision-Actions generalisieren
- typed `ui_actions` statt task-spezifischer UI-Sonderlogik
- generisches Action-Rendering im Frontend

## Prioritaet B - Workflow-Skalierung

1. Weitere Event-Templates
- mindestens 1 weiteres Event neben `birth_de`
- klare Fact-Dictionaries pro Event

2. Governance fuer Template-Releases
- Draft/Review/Publish-Prozess
- CI-Gates fuer Regression und Schema-Checks

3. Content-Qualitaet
- strukturierte Quellenpflege
- Sprach-/Rechts-Hinweise pro Task

## Prioritaet C - Betrieb und Plattform

1. Notifications/Reminder
- Worker fuer Deadline-Erinnerungen
- konfigurierbare Reminder-Regeln

2. Dokumentenmanagement
- Upload/Download-Flow mit S3-kompatiblem Storage
- Verknuepfung von Dokumenten mit Tasks

3. Observability
- strukturierte Logs, Metriken, Error-Tracking
- Dashboards fuer API/Worker/DB-Gesundheit

## Prioritaet D - DX und Qualitaet

1. Frontend-Linting standardisieren
- konsistente ESLint/Prettier-Konfiguration ohne interaktive Setup-Prompts

2. Testausbau
- End-to-End UI-Tests fuer Kernflows (z. B. Playwright)
- API-Contract-Tests fuer Response-Schemata (`task_kind`, Error-Codes)

3. Doku-Automatisierung
- API-Spec exportieren und versionieren
- Release-Notes aus Commits/PRs ableiten
