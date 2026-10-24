"""Turn date query parameters into UTC [start, end) ranges in the configured timezone."""

from datetime import date, datetime, timedelta

from ..config import get_settings
from ..errors import AppError
from .timecalc import date_range_bounds, day_bounds, local_date, preset_range

PRESETS = ("today", "week", "month")


def resolve_range(
    now: datetime,
    *,
    preset: str | None = None,
    on_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[datetime | None, datetime | None, dict]:
    """Returns (start, end, info). Priority: specific date, then explicit from/to, then preset.

    `to_date` is inclusive: the range ends at local midnight after it.
    """
    s = get_settings()
    tz = s.tz
    if on_date is not None:
        a, b = day_bounds(on_date, tz)
        return a, b, {"from": on_date.isoformat(), "to": on_date.isoformat()}
    if from_date is not None or to_date is not None:
        if from_date and to_date and from_date > to_date:
            raise AppError(422, "INVALID_DATE_RANGE", "The start date must be on or before the end date.",
                           {"to": "End date must be on or after the start date."})
        a = date_range_bounds(from_date, from_date, tz)[0] if from_date else None
        b = date_range_bounds(to_date, to_date, tz)[1] if to_date else None
        return a, b, {"from": from_date.isoformat() if from_date else None, "to": to_date.isoformat() if to_date else None}
    if preset in PRESETS:
        a, b = preset_range(preset, now, tz, s.week_start_weekday)
        last = local_date(b, tz) - timedelta(days=1)
        return a, b, {"from": local_date(a, tz).isoformat(), "to": last.isoformat(), "preset": preset}
    if preset not in (None, "", "all", "custom", "date"):
        raise AppError(422, "VALIDATION_ERROR", "Unknown date preset.", {"preset": "Unknown date preset."})
    return None, None, {"from": None, "to": None}
