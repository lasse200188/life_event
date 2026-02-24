# Roadmap: Blocked Tasks Completion Policy

## Ziel
Blockierte Tasks sollen standardmaessig **nicht** auf `done` gesetzt werden koennen. Ein bewusster Override soll moeglich sein, aber nur explizit und nachvollziehbar.

## Empfehlung (minimal + robust)
1. Backend als Source of Truth fuer Blockierungsregel.
2. API-Regel:
   - `PATCH /plans/{id}/tasks/{task_id}` mit `{ "status": "done" }` auf blockiertem Task => `409 Conflict` mit Fehlercode `TASK_BLOCKED`.
   - Mit `{ "status": "done", "force": true }` => erlaubt (`200`).
3. Task-Metadata erweitern:
   - `block_type: "hard" | "soft"` (Default: `hard`)
   - Optional spaeter statt `force` eine feiner granulare Policy.
4. Frontend:
   - Checkbox fuer blockierte Tasks standardmaessig disabled.
   - Bei Klick auf "Trotzdem erledigen" Modal mit Warnung und Confirm.
   - Confirm sendet `force: true`.

## Warum diese Variante
- Minimaler Eingriff: keine neue Frontend-Businesslogik, da Backend entscheidet.
- Klare API-Semantik: blockiert ist ein eigener Konfliktzustand (`409`).
- Zukunftssicher: `block_type` erlaubt spaeter differenzierte Regeln ohne API-Bruch.

## Umsetzungsplan

### Phase 1: Backend Policy
1. `TaskStatusPatchRequest` erweitern um `force: bool = False`.
2. In `TaskService.update_status(...)`:
   - Bei `status == done` und unresolved dependencies:
     - wenn nicht `force`: `ApiError(409, "TASK_BLOCKED", "...")`
     - sonst erlauben.
3. Dependencies fuer die Pruefung aus `task.metadata_json.blocked_by` lesen.
4. Optional: `block_type` aus `metadata_json` beruecksichtigen (`soft` kann ohne force erlaubt sein).

### Phase 2: Backend Tests
Service/API-Tests ergaenzen:
1. `test_cannot_complete_blocked_task_without_force()`
2. `test_can_force_complete_blocked_task()`
3. Optional:
   - `test_soft_block_can_complete_without_force()` (falls `soft` eingefuehrt wird)
   - `test_returns_409_and_task_blocked_error_code()`

### Phase 3: Frontend UX
1. Taskliste:
   - Blockiert-Badge beibehalten.
   - Checkbox disabled bei blockiert + hard block.
2. Override-Flow:
   - Button "Trotzdem als erledigt markieren".
   - Modal mit Warntext und Confirm.
   - Confirm sendet `PATCH` mit `force: true`.
3. Fehleranzeige:
   - Wenn Backend `TASK_BLOCKED` liefert, spezifische Meldung anzeigen.

### Phase 4: E2E (spaeter)
Empfehlung: Playwright (nahtlos mit Next.js).
Tests:
1. Blockierter Task laesst sich ohne Override nicht abschliessen.
2. Override-Modal -> Confirm -> Task wird `done`.
3. Refresh -> Status bleibt persistent.

## Offene Entscheidungen
1. Soll `soft` block ohne `force` sofort erlaubt sein?
2. Soll `force` ein `reason`-Feld erfordern (Audit/Transparenz)?
3. Sollen Overrides im Task-Log/Snapshot separat gespeichert werden?
