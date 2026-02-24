from __future__ import annotations

from datetime import date

import pytest

from app.planner.deadlines import compute_deadline, parse_iso_date
from app.planner.errors import PlannerInputError


def test_compute_deadline_negative_zero_positive_with_grace() -> None:
    event_date = date(2026, 4, 1)

    assert compute_deadline(event_date, -7).isoformat() == "2026-03-25"
    assert compute_deadline(event_date, 0).isoformat() == "2026-04-01"
    assert compute_deadline(event_date, 30).isoformat() == "2026-05-01"
    assert compute_deadline(event_date, 30, grace_days=2).isoformat() == "2026-05-03"


def test_parse_iso_date_accepts_date_only() -> None:
    assert parse_iso_date("2026-04-01") == date(2026, 4, 1)


def test_parse_iso_date_rejects_datetime_or_non_string() -> None:
    with pytest.raises(PlannerInputError, match="ISO date string"):
        parse_iso_date("2026-04-01T00:00:00Z")
    with pytest.raises(PlannerInputError, match="ISO date string"):
        parse_iso_date(20260401)
