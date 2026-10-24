"""Shared filter parsing and querying for the admin report, its totals and its exports."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from fastapi import Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..common import parse_oid
from ..enums import MandalName, MandalType
from ..reports.aggregation import combine, overlaps_range
from ..reports.filters import resolve_range
from ..sessions.service import status_match

SortField = Literal["date", "name", "username", "mandal_name", "mandal_type", "duration", "status"]
_SORT_KEYS = {
    "date": "clock_in",
    "name": "volunteer.full_name",
    "username": "volunteer.username_lower",
    "mandal_name": "mandal_name",
    "mandal_type": "mandal_type",
    "duration": "duration_seconds",
    "status": "status",
}


@dataclass
class ReportFilters:
    preset: str | None
    on_date: date | None
    from_date: date | None
    to_date: date | None
    mandal_name: MandalName | None
    mandal_type: MandalType | None
    q: str | None
    name: str | None
    username: str | None
    status: str
    user_id: str | None

    @property
    def include_active(self) -> bool:
        # Finalised reports exclude live sessions unless the Active filter is chosen.
        return self.status == "active"


def report_filters(
    preset: str | None = Query(None, description="today | week | month | date | custom"),
    date_: date | None = Query(None, alias="date", description="A specific local date"),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    mandal_name: MandalName | None = None,
    mandal_type: MandalType | None = None,
    q: str | None = Query(None, max_length=100, description="Volunteer name or username, partial"),
    name: str | None = Query(None, max_length=100),
    username: str | None = Query(None, max_length=64),
    status: Literal["all", "active", "completed", "flagged"] = "all",
    user_id: str | None = None,
) -> ReportFilters:
    return ReportFilters(preset, date_, from_, to, mandal_name, mandal_type, q, name, username, status, user_id)


def _contains(text: str) -> dict:
    return {"$regex": re.escape(text.strip()), "$options": "i"}


async def build_match(db: AsyncIOMotorDatabase, f: ReportFilters, now: datetime) -> tuple[dict, datetime | None, datetime | None, dict]:
    """Mongo match for seva_sessions plus the resolved [start, end) range and a description of it."""
    a, b, info = resolve_range(now, preset=f.preset, on_date=f.on_date, from_date=f.from_date, to_date=f.to_date)
    parts: list[dict] = [overlaps_range(a, b), status_match(f.status)]
    if f.mandal_name:
        parts.append({"mandal_name": f.mandal_name.value})
    if f.mandal_type:
        parts.append({"mandal_type": f.mandal_type.value})

    user_clauses: list[dict] = []
    if f.q and f.q.strip():
        user_clauses.append({"$or": [{"full_name": _contains(f.q)}, {"username_lower": _contains(f.q.lower())}]})
    if f.name and f.name.strip():
        user_clauses.append({"full_name": _contains(f.name)})
    if f.username and f.username.strip():
        user_clauses.append({"username_lower": _contains(f.username.lower())})
    if user_clauses:
        ids = [u["_id"] async for u in db.users.find(combine(*user_clauses), {"_id": 1})]
        parts.append({"user_id": {"$in": ids}})
    if f.user_id:
        parts.append({"user_id": parse_oid(f.user_id, "Volunteer")})
    return combine(*parts), a, b, info


def report_pipeline(match: dict, sort: str, order: str, skip: int | None = None, limit: int | None = None) -> list[dict]:
    direction = 1 if order == "asc" else -1
    pipeline: list[dict] = [
        {"$match": match},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "volunteer"}},
        {"$unwind": "$volunteer"},
        {"$sort": {_SORT_KEYS[sort]: direction, "_id": direction}},
    ]
    if skip:
        pipeline.append({"$skip": skip})
    if limit:
        pipeline.append({"$limit": limit})
    pipeline.append({"$project": {"volunteer.password_hash": 0}})
    return pipeline


def describe(f: ReportFilters, info: dict) -> str:
    """'This month · All Mandals · All Types' style label for headers and exports."""
    labels = {"today": "Today", "week": "This week", "month": "This month"}
    if info.get("preset") in labels:
        when = labels[info["preset"]]
    elif info.get("from") and info.get("to"):
        when = info["from"] if info["from"] == info["to"] else f"{info['from']} to {info['to']}"
    elif info.get("from"):
        when = f"From {info['from']}"
    elif info.get("to"):
        when = f"Until {info['to']}"
    else:
        when = "All time"
    parts = [
        when,
        f.mandal_name.value if f.mandal_name else "All Mandals",
        f.mandal_type.value if f.mandal_type else "All Types",
    ]
    if f.status != "all":
        parts.append(f.status.capitalize())
    return " · ".join(parts)
