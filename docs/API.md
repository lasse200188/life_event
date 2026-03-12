# API Reference (Current)

Basis-URL lokal: `http://localhost:8000`

## Health

### `GET /health`

Antwort:
```json
{ "status": "ok" }
```

## Plans

### `POST /plans`

Erzeugt einen neuen Plan aus Template + Facts.

Request:
```json
{
  "template_key": "birth_de/v2",
  "facts": {
    "birth_date": "2026-04-01",
    "employment_type": "employed"
  }
}
```

Antwort: `201 Created`
- `id`, `template_key`, `status`, `created_at`, `updated_at`, `links`

### `GET /plans/{plan_id}`

Query:
- `include_snapshot` (`true|false`, default `false`)

Antwort:
- Plan-Grunddaten
- `snapshot_meta`
- optional `snapshot`

Bei `include_snapshot=true` enthaelt `snapshot` u. a.:
- `template_version`
- `fact_schema_version`
- `facts_hash`
- optional bei Recompute:
  - `recompute.executed_at`
  - `recompute.reason` (`MANUAL|FACT_CHANGE|TEMPLATE_UPDATE`)
  - `recompute_delta` mit Task-/Fact-Aenderungen

### `PATCH /plans/{plan_id}/facts`

Merged Facts-Update auf einem bestehenden Plan.

Request:
```json
{
  "facts": {
    "child_insurance_kind": "gkv"
  },
  "recompute": true
}
```

Verhalten:
- merged Facts werden gespeichert
- bei `recompute=true` wird Plan neu berechnet
- Recompute bei Facts-Update nutzt intern `reason=FACT_CHANGE`

### `POST /plans/{plan_id}/recompute`

Fuehrt Recompute fuer aktuellen Facts-Stand aus.

Query:
- `reason` (`FACT_CHANGE|TEMPLATE_UPDATE|MANUAL`, default `MANUAL`)

Verhalten:
- aktive Tasks werden per Merge mit bestehenden Instanzen abgeglichen (`task_key`)
- nicht mehr eligible Tasks werden auf `skipped` gesetzt (soft-dismiss), nicht geloescht
- bereits erledigte Tasks bleiben `done`
- Snapshot enthaelt Recompute-Metadaten (`reason`) und Delta

## Tasks

### `GET /plans/{plan_id}/tasks`

Query:
- `status` (optional)
- `include_metadata` (`true|false`, default `false`)

Antwort (pro Task):
- `id`, `plan_id`, `task_key`, `title`, `description`
- `task_kind`: `normal | decision`
- `status`, `due_date`, `sort_key`, Timestamps
- optional `metadata`

Hinweis:
- Recompute kann Tasks auf `skipped` setzen (soft-dismiss), statt sie zu loeschen.

`task_kind` wird serverseitig berechnet:
- `decision`, wenn `metadata.tags` `decision` enthaelt oder `metadata.ui_actions` gesetzt ist
- sonst `normal`

### `PATCH /plans/{plan_id}/tasks/{task_id}`

Request:
```json
{
  "status": "done",
  "force": false
}
```

Verhalten:
- blockierte hard-dependencies -> `409 TASK_BLOCKED` (außer `force=true`)
- Decision-Tasks koennen nicht manuell auf `done` gesetzt werden -> `409 TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN`

## Error Model

Alle Domain-Fehler folgen:
```json
{
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

Typische Codes:
- `TEMPLATE_NOT_FOUND`
- `PLAN_NOT_FOUND`
- `TASK_NOT_FOUND`
- `TASK_BLOCKED`
- `TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN`
- `PLANNER_INPUT_INVALID`
- `PERSISTENCE_ERROR`
- `REQUEST_VALIDATION_ERROR`

## Notifications

### `PUT /plans/{plan_id}/notification-profile`

Setzt Reminder-Einstellungen fuer einen Plan (MVP ohne Auth).

Request:
```json
{
  "email": "user@example.com",
  "email_consent": true,
  "locale": "de-DE",
  "timezone": "Europe/Berlin",
  "reminder_due_soon_enabled": true
}
```

Antwort:
- Profil-Stammdaten
- `sendable` (true nur wenn email vorhanden, consent=true, nicht unsubscribed, reminder enabled)

Hinweise:
- `email_consent=false` setzt **nicht** automatisch `unsubscribed_at`.
- Daily cap fuer Reminder basiert auf bereits `sent` Remindern pro Profil/Tag.

### `GET /notifications/unsubscribe?token=...`

Token-basierter Opt-out fuer Reminder-Mails.

Antwort:
```json
{ "ok": true }
```

Hinweise:
- Endpoint ist idempotent (mehrfaches Klicken bleibt stabil).
- Token ist pro Profil stabil und kann serverseitig gezielt rotiert werden.
