"""Volunteer endpoints. Every query is scoped to the signed-in user; other users' sessions return 404."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..audit.service import audit_public
from ..auth.deps import db_dep, get_current_user
from ..common import page_meta, page_params, parse_oid, utcnow
from ..errors import not_found
from ..reports.aggregation import combine, overlaps_range, range_total, time_buckets
from ..reports.filters import resolve_range
from ..reports.timecalc import duration_view
from . import service
from .schemas import ManualSessionIn, PreviewIn, SessionUpdateIn

router = APIRouter(prefix="/api/me", tags=["volunteer"])

StatusFilter = Literal["all", "active", "completed", "flagged"]


async def _own_session(db: AsyncIOMotorDatabase, user: dict, session_id: str) -> dict:
    doc = await db.seva_sessions.find_one({"_id": parse_oid(session_id, "Session"), "user_id": user["_id"]})
    if doc is None:
        raise not_found("Session")
    return doc


@router.get("/summary")
async def summary(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now = utcnow()
    mine = {"user_id": user["_id"]}
    out = {}
    for key, preset in (("today", "today"), ("week", "week"), ("month", "month")):
        a, b, info = resolve_range(now, preset=preset)
        t = await range_total(db, mine, a, b, now, include_active=True)
        out[key] = {**info, "duration": duration_view(t["seconds"]), "sessions": t["sessions"]}
    life = await range_total(db, mine, None, None, now, include_active=True)
    out["lifetime"] = {"duration": duration_view(life["seconds"]), "sessions": life["sessions"]}
    active = await service.get_active_session(db, user["_id"])
    recent = await db.seva_sessions.find(mine).sort("clock_in", -1).limit(5).to_list(5)
    return {
        "now": now.isoformat(),
        "active_session": service.session_public(active, now) if active else None,
        "totals": out,
        "recent": [service.session_public(r, now) for r in recent],
    }


@router.get("/sessions")
async def list_sessions(
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    preset: str | None = None,
    status: StatusFilter = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    now = utcnow()
    a, b, info = resolve_range(now, preset=preset, from_date=from_, to_date=to)
    match = combine({"user_id": user["_id"]}, service.status_match(status), overlaps_range(a, b))
    skip, limit = page_params(page, page_size)
    total = await db.seva_sessions.count_documents(match)
    docs = await db.seva_sessions.find(match).sort("clock_in", -1).skip(skip).limit(limit).to_list(limit)
    totals = await range_total(db, combine({"user_id": user["_id"]}, service.status_match(status)), a, b, now, include_active=True)
    return {
        "items": [service.session_public(d, now) for d in docs],
        "range": info,
        "summary": {"duration": duration_view(totals["seconds"]), "sessions": totals["sessions"]},
        **page_meta(page, page_size, total),
    }


@router.get("/totals")
async def totals(
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    preset: str | None = None,
    group: Literal["day", "week", "month"] = "day",
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    now = utcnow()
    a, b, info = resolve_range(now, preset=preset or "month", from_date=from_, to_date=to)
    mine = {"user_id": user["_id"]}
    total = await range_total(db, mine, a, b, now, include_active=True)
    buckets = await time_buckets(db, mine, a, b, now, True, group) if a and b else {}
    return {
        "range": info,
        "group": group,
        "duration": duration_view(total["seconds"]),
        "sessions": total["sessions"],
        "buckets": [{"start": d.isoformat(), **duration_view(v)} for d, v in sorted(buckets.items())],
    }


@router.post("/sessions/clock-in", status_code=201)
async def clock_in(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await service.clock_in(db, user)
    return {"session": service.session_public(doc)}


@router.post("/sessions/clock-out")
async def clock_out(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await service.clock_out(db, user)
    return {"session": service.session_public(doc)}


@router.post("/sessions", status_code=201)
async def create_manual(body: ManualSessionIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await service.create_manual(
        db, user, clock_in=body.clock_in, clock_out=body.clock_out, reason=body.reason, confirm_overlap=body.confirm_overlap
    )
    return {"session": service.session_public(doc)}


@router.post("/sessions/preview")
async def preview(body: PreviewIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    exclude = None
    if body.session_id:
        exclude = (await _own_session(db, user, body.session_id))["_id"]
    return await service.preview(db, user["_id"], clock_in=body.clock_in, clock_out=body.clock_out, exclude_id=exclude)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await _own_session(db, user, session_id)
    return {"session": service.session_public(doc)}


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str, body: SessionUpdateIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    doc = await _own_session(db, user, session_id)
    updated = await service.update_times(
        db, doc, user, clock_in=body.clock_in, clock_out=body.clock_out, reason=body.reason, confirm_overlap=body.confirm_overlap
    )
    return {"session": service.session_public(updated)}


@router.get("/sessions/{session_id}/audit")
async def session_audit(session_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await _own_session(db, user, session_id)
    logs = await db.audit_logs.find({"entity": "seva_session", "entity_id": doc["_id"]}).sort([("created_at", -1), ("_id", -1)]).to_list(200)
    return {"items": [audit_public(x) for x in logs]}

