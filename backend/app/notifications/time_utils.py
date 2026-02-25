from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

BERLIN_TZ = ZoneInfo("Europe/Berlin")
QUIET_HOURS_START = time(hour=8, minute=0)
QUIET_HOURS_END = time(hour=20, minute=0)


def now_berlin() -> datetime:
    return datetime.now(BERLIN_TZ)


def is_within_send_window(dt: datetime) -> bool:
    local = dt.astimezone(BERLIN_TZ).time()
    return QUIET_HOURS_START <= local <= QUIET_HOURS_END


def next_send_window_start(dt: datetime) -> datetime:
    local_dt = dt.astimezone(BERLIN_TZ)
    local_time = local_dt.time()

    if local_time < QUIET_HOURS_START:
        return local_dt.replace(
            hour=QUIET_HOURS_START.hour,
            minute=QUIET_HOURS_START.minute,
            second=0,
            microsecond=0,
        )

    next_day = (local_dt + timedelta(days=1)).replace(
        hour=QUIET_HOURS_START.hour,
        minute=QUIET_HOURS_START.minute,
        second=0,
        microsecond=0,
    )
    return next_day


def due_soon_window(dt: datetime) -> tuple[str, str]:
    today = dt.astimezone(BERLIN_TZ).date()
    end = today + timedelta(days=3)
    return today.isoformat(), end.isoformat()
