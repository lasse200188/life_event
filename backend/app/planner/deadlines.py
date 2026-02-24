from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.planner.errors import PlannerInputError


def parse_iso_date(value: Any) -> date:
    if not isinstance(value, str):
        raise PlannerInputError("event_date must be an ISO date string (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PlannerInputError(
            "event_date must be an ISO date string (YYYY-MM-DD)"
        ) from exc


def compute_deadline(event_date: date, relative_days: int, grace_days: int = 0) -> date:
    if not isinstance(relative_days, int):
        raise PlannerInputError("offset_days must be int")
    if not isinstance(grace_days, int):
        raise PlannerInputError("grace_days must be int")
    return event_date + timedelta(days=relative_days + grace_days)
