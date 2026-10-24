"""Totals over seva sessions. All arithmetic goes through timecalc so every screen uses the same rules.

Sessions are streamed with a narrow projection and clipped in Python. This keeps the clipping and
midnight-split rules in one tested place. Volume is fine for a volunteer organisation (tens of
thousands of sessions); Mongo indexes on clock_in keep the candidate set small.
"""

from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Hashable
from datetime import date, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import get_settings
from ..enums import SessionStatus
from .timecalc import bucket_totals, clip_seconds, ensure_utc

_PROJECTION = {"user_id": 1, "mandal_name": 1, "mandal_type": 1, "clock_in": 1, "clock_out": 1, "status": 1}


def overlaps_range(range_start: datetime | None, range_end: datetime | None) -> dict:
    """Mongo filter for sessions that overlap [range_start, range_end). Open sessions have clock_out None."""
    clauses: list[dict] = []
    if range_end is not None:
        clauses.append({"clock_in": {"$lt": range_end}})
    if range_start is not None:
        clauses.append({"$or": [{"clock_out": {"$gt": range_start}}, {"clock_out": None}]})
    return {"$and": clauses} if clauses else {}


def combine(*filters: dict) -> dict:
    parts = [f for f in filters if f]
    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


async def iter_intervals(
    db: AsyncIOMotorDatabase, match: dict, now: datetime, include_active: bool
) -> AsyncIterator[tuple[dict, datetime, datetime]]:
    """Yield (doc, start, end). Active sessions end at `now` when included, otherwise are skipped."""
    async for doc in db.seva_sessions.find(match, _PROJECTION):
        if doc.get("clock_out"):
            yield doc, ensure_utc(doc["clock_in"]), ensure_utc(doc["clock_out"])
        elif include_active and doc.get("status") == SessionStatus.ACTIVE.value:
            yield doc, ensure_utc(doc["clock_in"]), ensure_utc(now)


async def range_total(
    db: AsyncIOMotorDatabase,
    match: dict,
    range_start: datetime | None,
    range_end: datetime | None,
    now: datetime,
    include_active: bool,
) -> dict:
    """{"seconds", "sessions", "volunteers"} for sessions matching `match`, clipped to the range."""
    full = combine(match, overlaps_range(range_start, range_end))
    seconds = 0
    sessions = 0
    users = set()
    async for doc, start, end in iter_intervals(db, full, now, include_active):
        secs = clip_seconds(start, end, range_start, range_end)
        seconds += secs
        sessions += 1
        users.add(doc["user_id"])
    return {"seconds": seconds, "sessions": sessions, "volunteers": len(users)}


async def grouped_totals(
    db: AsyncIOMotorDatabase,
    match: dict,
    range_start: datetime | None,
    range_end: datetime | None,
    now: datetime,
    include_active: bool,
    key: Callable[[dict], Hashable],
) -> dict[Hashable, dict]:
    full = combine(match, overlaps_range(range_start, range_end))
    out: dict[Hashable, dict] = defaultdict(lambda: {"seconds": 0, "sessions": 0})
    async for doc, start, end in iter_intervals(db, full, now, include_active):
        bucket = out[key(doc)]
        bucket["seconds"] += clip_seconds(start, end, range_start, range_end)
        bucket["sessions"] += 1
    return dict(out)


async def time_buckets(
    db: AsyncIOMotorDatabase,
    match: dict,
    range_start: datetime,
    range_end: datetime,
    now: datetime,
    include_active: bool,
    group: str,
) -> dict[date, int]:
    """Seconds per local day/week/month. Sessions crossing midnight are split across days."""
    s = get_settings()
    full = combine(match, overlaps_range(range_start, range_end))
    intervals = [(start, end) async for _, start, end in iter_intervals(db, full, now, include_active)]
    return bucket_totals(intervals, s.tz, group, range_start, range_end, s.week_start_weekday)
