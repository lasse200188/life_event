from __future__ import annotations

from datetime import date
from uuid import UUID


def build_due_soon_dedupe_key_raw(*, profile_id: UUID, local_day: date) -> str:
    return f"task_due_soon|email|profile:{profile_id}|{local_day.isoformat()}"
