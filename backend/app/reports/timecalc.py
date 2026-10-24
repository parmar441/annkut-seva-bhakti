"""Pure time math for seva hours. No database access here, so it is easy to test.

Rules (SPEC §6):
- Everything is stored and aggregated in whole seconds.
- A session contributes max(0, min(end, B) - max(start, A)) to a range [A, B).
- Daily totals split sessions at local midnight in the configured timezone.
- Decimal hours round half-up to 2 places, "h m" format floors to minutes.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def duration_seconds(start: datetime, end: datetime) -> int:
    """Whole seconds between two instants (floored). Negative if end < start."""
    delta = ensure_utc(end) - ensure_utc(start)
    return int(delta.total_seconds() // 1)


def clip_seconds(start: datetime, end: datetime, range_start: datetime | None, range_end: datetime | None) -> int:
    """Seconds of [start, end) that fall inside [range_start, range_end). None means unbounded."""
    s = ensure_utc(start)
    e = ensure_utc(end)
    if range_start is not None:
        s = max(s, ensure_utc(range_start))
    if range_end is not None:
        e = min(e, ensure_utc(range_end))
    return max(0, duration_seconds(s, e))


def local_midnight(d: date, tz: ZoneInfo) -> datetime:
    """The UTC instant of local midnight at the start of day d."""
    return datetime.combine(d, time(0), tzinfo=tz).astimezone(UTC)


def day_bounds(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) of a local calendar day in UTC. 23 or 25 hours long on DST change days."""
    return local_midnight(d, tz), local_midnight(d + timedelta(days=1), tz)


def date_range_bounds(start: date, end_inclusive: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return local_midnight(start, tz), local_midnight(end_inclusive + timedelta(days=1), tz)


def local_date(dt: datetime, tz: ZoneInfo) -> date:
    return ensure_utc(dt).astimezone(tz).date()


def split_by_local_day(start: datetime, end: datetime, tz: ZoneInfo) -> dict[date, int]:
    """Seconds per local calendar day for one session. Crosses-midnight sessions span several keys."""
    out: dict[date, int] = {}
    s, e = ensure_utc(start), ensure_utc(end)
    if e <= s:
        return out
    d = local_date(s, tz)
    while True:
        day_start, day_end = day_bounds(d, tz)
        if day_start >= e:
            break
        secs = clip_seconds(s, e, day_start, day_end)
        if secs > 0:
            out[d] = secs
        d += timedelta(days=1)
    return out


def week_start_date(d: date, week_start_weekday: int) -> date:
    """First day of the week containing d. week_start_weekday uses Python weekday() (Mon=0, Sun=6)."""
    return d - timedelta(days=(d.weekday() - week_start_weekday) % 7)


def month_start_date(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def preset_range(preset: str, now: datetime, tz: ZoneInfo, week_start_weekday: int = 6) -> tuple[datetime, datetime]:
    """UTC [start, end) for today / week / month in the local timezone."""
    today = local_date(now, tz)
    if preset == "today":
        return day_bounds(today, tz)
    if preset == "week":
        ws = week_start_date(today, week_start_weekday)
        return local_midnight(ws, tz), local_midnight(ws + timedelta(days=7), tz)
    if preset == "month":
        ms = month_start_date(today)
        return local_midnight(ms, tz), local_midnight(next_month(ms), tz)
    raise ValueError(f"Unknown preset: {preset}")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


def intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open intervals overlap when each starts before the other ends. Touching end-to-start is fine."""
    return ensure_utc(a_start) < ensure_utc(b_end) and ensure_utc(b_start) < ensure_utc(a_end)


def bucket_totals(
    sessions: Iterable[tuple[datetime, datetime]],
    tz: ZoneInfo,
    group: str,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    week_start_weekday: int = 6,
) -> dict[date, int]:
    """Totals per day/week/month bucket, keyed by the bucket's first local date.

    Sessions are first clipped to [range_start, range_end), then split at local midnight,
    so nothing is double counted and each second lands in exactly one bucket.
    """
    out: dict[date, int] = defaultdict(int)
    for start, end in sessions:
        s = max(ensure_utc(start), ensure_utc(range_start)) if range_start else ensure_utc(start)
        e = min(ensure_utc(end), ensure_utc(range_end)) if range_end else ensure_utc(end)
        for d, secs in split_by_local_day(s, e, tz).items():
            if group == "day":
                key = d
            elif group == "week":
                key = week_start_date(d, week_start_weekday)
            elif group == "month":
                key = month_start_date(d)
            else:
                raise ValueError(f"Unknown group: {group}")
            out[key] += secs
    return dict(out)


# ---------- display formatting (same rule everywhere) ----------


def decimal_hours(seconds: int) -> Decimal:
    """Hours rounded half-up to 2 decimal places."""
    return (Decimal(int(seconds)) / Decimal(3600)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_decimal_hours(seconds: int) -> str:
    """'2.5 h', '186.75 h', '0 h'. Trailing zeros are trimmed."""
    text = f"{decimal_hours(seconds):.2f}".rstrip("0").rstrip(".")
    return f"{text} h"


def hours_minutes(seconds: int) -> tuple[int, int]:
    total_minutes = max(0, int(seconds)) // 60
    return total_minutes // 60, total_minutes % 60


def format_hm_short(seconds: int) -> str:
    """'2h 30m', '45m', '0m'."""
    h, m = hours_minutes(seconds)
    if h == 0:
        return f"{m}m"
    return f"{h}h {m}m"


def format_hm_long(seconds: int) -> str:
    """'2 hours 30 minutes', '1 hour', '45 minutes', '0 minutes'."""
    h, m = hours_minutes(seconds)
    parts = []
    if h:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m or not h:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    return " ".join(parts)


def duration_view(seconds: int | None) -> dict | None:
    if seconds is None:
        return None
    return {
        "seconds": int(seconds),
        "hm": format_hm_short(seconds),
        "long": format_hm_long(seconds),
        "decimal": float(decimal_hours(seconds)),
        "decimal_text": format_decimal_hours(seconds),
    }
