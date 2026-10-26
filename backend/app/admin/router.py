"""Admin endpoints. The router-level dependency enforces require_admin on every route."""

import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from ..audit.service import audit_public, write_audit
from ..auth.deps import db_dep, require_admin
from ..auth.tokens import revoke_all_for_user
from ..config import get_settings
from ..common import iso, page_meta, page_params, parse_oid, utcnow
from ..enums import AuditAction, MandalName, MandalType, Role, SessionFlag, SessionStatus
from ..errors import AppError, not_found
from ..reports.aggregation import combine, grouped_totals, overlaps_range, range_total, time_buckets
from ..reports.filters import resolve_range
from ..reports.timecalc import duration_view, local_date
from ..sessions import service as sessions
from ..sessions.schemas import CorrectionIn, MarkReviewedIn, PreviewIn
from ..users.service import user_public
from . import export
from .report_query import ReportFilters, SortField, build_match, describe, report_filters, report_pipeline

REPORT_PAGE_SIZES = (20, 50, 100)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _volunteer(v: dict | None) -> dict | None:
    if not v:
        return None
    return {"id": str(v["_id"]), "full_name": v["full_name"], "username": v["username"],
            "mandal_name": v["mandal_name"], "mandal_type": v["mandal_type"], "is_active": v["is_active"]}


def _row(doc: dict, now) -> dict:
    return {**sessions.session_public(doc, now), "volunteer": _volunteer(doc.get("volunteer"))}


async def _with_volunteers(db: AsyncIOMotorDatabase, docs: list[dict]) -> list[dict]:
    ids = list({d["user_id"] for d in docs})
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": ids}}, {"password_hash": 0})}
    for d in docs:
        d["volunteer"] = users.get(d["user_id"])
    return docs


# ---------- dashboard ----------


@router.get("/stats")
async def stats(db: AsyncIOMotorDatabase = Depends(db_dep)):
    now = utcnow()
    await sessions.sweep_missing_clock_outs(db, now)
    volunteers = {"role": Role.USER.value}
    total_volunteers = await db.users.count_documents(volunteers)
    active_accounts = await db.users.count_documents({**volunteers, "is_active": True})
    completed = {"status": SessionStatus.COMPLETED.value}
    completed_sessions = await db.seva_sessions.count_documents(completed)
    all_time = await range_total(db, completed, None, None, now, include_active=False)

    # Live figures: active sessions count toward today and this month up to now.
    a_today, b_today, _ = resolve_range(now, preset="today")
    today = await range_total(db, {}, a_today, b_today, now, include_active=True)
    a_month, b_month, month_info = resolve_range(now, preset="month")
    month = await range_total(db, {}, a_month, b_month, now, include_active=True)
    by_mandal = await grouped_totals(db, {}, a_month, b_month, now, True, lambda d: d["mandal_name"])
    by_type = await grouped_totals(db, {}, a_month, b_month, now, True, lambda d: d["mandal_type"])

    on_seva_now = await db.seva_sessions.count_documents({"status": SessionStatus.ACTIVE.value})
    review_total = await db.seva_sessions.count_documents({"needs_review": True})
    review_by_flag = {
        f.value: await db.seva_sessions.count_documents({"needs_review": True, "flags": f.value}) for f in SessionFlag
    }
    empty = {"seconds": 0, "sessions": 0}
    return {
        "now": iso(now),
        "month": month_info,
        "total_volunteers": total_volunteers,
        "active_accounts": active_accounts,
        "completed_sessions": completed_sessions,
        "total_hours": duration_view(all_time["seconds"]),
        "hours_today": duration_view(today["seconds"]),
        "volunteers_today": today["volunteers"],
        "hours_this_month": duration_view(month["seconds"]),
        "on_seva_now": on_seva_now,
        "needs_review": {"total": review_total, "by_flag": review_by_flag},
        "password_reset_requests": await db.password_resets.count_documents({"active": True, "status": "requested"}),
        "by_mandal": [{"name": m.value, **duration_view(by_mandal.get(m.value, empty)["seconds"])} for m in MandalName],
        "by_type": [{"name": t.value, **duration_view(by_type.get(t.value, empty)["seconds"])} for t in MandalType],
    }


# ---------- volunteers ----------


@router.get("/users")
async def list_users(
    q: str | None = Query(None, max_length=100),
    mandal_name: MandalName | None = None,
    mandal_type: MandalType | None = None,
    is_active: bool | None = None,
    role: Literal["user", "admin", "all"] = "user",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    match: dict = {}
    if role != "all":
        match["role"] = role
    if q and q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        match["$or"] = [{"full_name": pattern}, {"username_lower": {"$regex": re.escape(q.strip().lower())}}]
    if mandal_name:
        match["mandal_name"] = mandal_name.value
    if mandal_type:
        match["mandal_type"] = mandal_type.value
    if is_active is not None:
        match["is_active"] = is_active
    skip, limit = page_params(page, page_size)
    total = await db.users.count_documents(match)
    users = await db.users.find(match, {"password_hash": 0}).sort("full_name", 1).skip(skip).limit(limit).to_list(limit)
    ids = [u["_id"] for u in users]
    lifetime = {
        r["_id"]: r["seconds"]
        async for r in db.seva_sessions.aggregate(
            [
                {"$match": {"user_id": {"$in": ids}, "status": SessionStatus.COMPLETED.value}},
                {"$group": {"_id": "$user_id", "seconds": {"$sum": "$duration_seconds"}}},
            ]
        )
    }
    active = {s["user_id"] async for s in db.seva_sessions.find({"user_id": {"$in": ids}, "status": "active"}, {"user_id": 1})}
    resets = {r["user_id"]: r["status"] async for r in db.password_resets.find({"user_id": {"$in": ids}, "active": True})}
    items = [
        {**user_public(u), "lifetime": duration_view(int(lifetime.get(u["_id"], 0))), "on_seva_now": u["_id"] in active,
         "password_reset": resets.get(u["_id"])}
        for u in users
    ]
    return {"items": items, **page_meta(page, page_size, total)}


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")})
    if user is None:
        raise not_found("Volunteer")
    now = utcnow()
    mine = {"user_id": user["_id"]}
    lifetime = await range_total(db, {**mine, "status": SessionStatus.COMPLETED.value}, None, None, now, False)
    a, b, _ = resolve_range(now, preset="month")
    month = await range_total(db, mine, a, b, now, include_active=True)
    active = await sessions.get_active_session(db, user["_id"])
    return {
        "user": user_public(user),
        "lifetime": {"duration": duration_view(lifetime["seconds"]), "sessions": lifetime["sessions"]},
        "this_month": {"duration": duration_view(month["seconds"]), "sessions": month["sessions"]},
        "active_session": sessions.session_public(active, now) if active else None,
        "needs_review": await db.seva_sessions.count_documents({**mine, "needs_review": True}),
    }


class StatusIn(BaseModel):
    is_active: bool
    reason: str | None = None


@router.patch("/users/{user_id}/status")
async def set_user_status(
    user_id: str, body: StatusIn, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")})
    if user is None:
        raise not_found("Volunteer")
    if user["_id"] == admin["_id"] and not body.is_active:
        raise AppError(409, "CANNOT_DEACTIVATE_SELF", "You can't deactivate your own account.")
    if user["is_active"] == body.is_active:
        return {"user": user_public(user)}
    now = utcnow()
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": body.is_active, "updated_at": now}})
    if not body.is_active:
        await revoke_all_for_user(db, user["_id"])
    await write_audit(
        db, entity="user", entity_id=user["_id"],
        action=AuditAction.ACTIVATE if body.is_active else AuditAction.DEACTIVATE, actor=admin,
        before={"is_active": user["is_active"]}, after={"is_active": body.is_active}, reason=body.reason,
        owner_id=user["_id"],
    )
    user["is_active"] = body.is_active
    return {"user": user_public(user)}


@router.get("/users/{user_id}/sessions")
async def user_sessions(
    user_id: str,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")}, {"_id": 1})
    if user is None:
        raise not_found("Volunteer")
    now = utcnow()
    a, b, info = resolve_range(now, from_date=from_, to_date=to)
    match = combine({"user_id": user["_id"]}, overlaps_range(a, b))
    skip, limit = page_params(page, page_size)
    total = await db.seva_sessions.count_documents(match)
    docs = await db.seva_sessions.find(match).sort("clock_in", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": [sessions.session_public(d, now) for d in docs], "range": info, **page_meta(page, page_size, total)}


# ---------- reports ----------


@router.get("/sessions")
async def report(
    filters: ReportFilters = Depends(report_filters),
    sort: SortField = "date",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, description="20, 50 or 100"),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    if page_size not in REPORT_PAGE_SIZES:
        raise AppError(422, "VALIDATION_ERROR", "Page size must be 20, 50 or 100.", {"page_size": "Choose 20, 50 or 100."})
    now = utcnow()
    match, a, b, info = await build_match(db, filters, now)
    skip, limit = page_params(page, page_size)
    total = await db.seva_sessions.count_documents(match)
    docs = await db.seva_sessions.aggregate(report_pipeline(match, sort, order, skip, limit)).to_list(limit)
    totals = await range_total(db, match, a, b, now, filters.include_active)
    return {
        "items": [_row(d, now) for d in docs],
        "range": info,
        "label": describe(filters, info),
        "totals": {"duration": duration_view(totals["seconds"]), "sessions": total, "volunteers": totals["volunteers"]},
        "include_active_in_totals": filters.include_active,
        **page_meta(page, page_size, total),
    }


@router.get("/sessions/export")
async def export_report(
    format: Literal["csv", "xlsx"] = "csv",
    filters: ReportFilters = Depends(report_filters),
    sort: SortField = "date",
    order: Literal["asc", "desc"] = "desc",
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    now = utcnow()
    match, a, b, info = await build_match(db, filters, now)
    total = await range_total(db, match, a, b, now, filters.include_active)
    total["sessions"] = await db.seva_sessions.count_documents(match)
    by_mandal = await grouped_totals(db, match, a, b, now, filters.include_active, lambda d: d["mandal_name"])
    by_type = await grouped_totals(db, match, a, b, now, filters.include_active, lambda d: d["mandal_type"])
    summary = export.summary_rows(describe(filters, info), total, by_mandal, by_type, now)
    rows = export.iter_report_rows(db, report_pipeline(match, sort, order))
    stamp = local_date(now, get_settings().tz).isoformat()
    if format == "csv":
        return StreamingResponse(
            export.stream_csv(rows, summary),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="seva-report-{stamp}.csv"'},
        )
    f = await export.build_xlsx(rows, summary)
    return StreamingResponse(
        export.iter_file(f),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="seva-report-{stamp}.xlsx"'},
    )


@router.get("/totals")
async def totals(
    group_by: Literal["volunteer", "mandal_name", "mandal_type", "day", "week", "month"] = "mandal_name",
    filters: ReportFilters = Depends(report_filters),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    now = utcnow()
    match, a, b, info = await build_match(db, filters, now)
    if group_by in ("day", "week", "month"):
        if a is None or b is None:
            raise AppError(422, "VALIDATION_ERROR", "Choose a date range to group by time.", {"from": "Choose a date range."})
        buckets = await time_buckets(db, match, a, b, now, filters.include_active, group_by)
        items = [{"key": d.isoformat(), "label": d.isoformat(), **duration_view(v)} for d, v in sorted(buckets.items())]
        return {"group_by": group_by, "range": info, "items": items}

    if group_by == "volunteer":
        grouped = await grouped_totals(db, match, a, b, now, filters.include_active, lambda d: d["user_id"])
        users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": list(grouped)}}, {"full_name": 1, "username": 1})}
        items = [
            {"key": str(k), "label": users[k]["full_name"] if k in users else "Unknown",
             "username": users.get(k, {}).get("username"), "sessions": v["sessions"], **duration_view(v["seconds"])}
            for k, v in grouped.items()
        ]
        items.sort(key=lambda x: -x["seconds"])
    else:
        grouped = await grouped_totals(db, match, a, b, now, filters.include_active, lambda d: d[group_by])
        names = [m.value for m in (MandalName if group_by == "mandal_name" else MandalType)]
        empty = {"seconds": 0, "sessions": 0}
        items = [{"key": n, "label": n, "sessions": grouped.get(n, empty)["sessions"],
                  **duration_view(grouped.get(n, empty)["seconds"])} for n in names]
    return {"group_by": group_by, "range": info, "label": describe(filters, info), "items": items}


# ---------- review queue and corrections ----------

ReviewType = Literal["all", "missing_clock_out", "overlap", "long_session", "manual_entry"]


@router.get("/review")
async def review_queue(
    type: ReviewType = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    now = utcnow()
    await sessions.sweep_missing_clock_outs(db, now)
    match: dict = {"needs_review": True}
    if type != "all":
        match["flags"] = type
    skip, limit = page_params(page, page_size)
    total = await db.seva_sessions.count_documents(match)
    docs = await db.seva_sessions.find(match).sort("clock_in", -1).skip(skip).limit(limit).to_list(limit)
    await _with_volunteers(db, docs)
    other_ids = list({oid for d in docs for oid in d.get("overlap_with", [])})
    others = {o["_id"]: o async for o in db.seva_sessions.find({"_id": {"$in": other_ids}})}
    items = []
    for d in docs:
        row = _row(d, now)
        row["overlaps"] = [sessions.session_public(others[o], now) for o in d.get("overlap_with", []) if o in others]
        items.append(row)
    counts = {f.value: await db.seva_sessions.count_documents({"needs_review": True, "flags": f.value}) for f in SessionFlag}
    counts["all"] = await db.seva_sessions.count_documents({"needs_review": True})
    return {"items": items, "counts": counts, **page_meta(page, page_size, total)}


async def _session(db: AsyncIOMotorDatabase, session_id: str) -> dict:
    doc = await db.seva_sessions.find_one({"_id": parse_oid(session_id, "Session")})
    if doc is None:
        raise not_found("Session")
    return doc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = (await _with_volunteers(db, [await _session(db, session_id)]))[0]
    return {"session": _row(doc, utcnow())}


@router.post("/sessions/{session_id}/preview")
async def preview_correction(session_id: str, body: PreviewIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await _session(db, session_id)
    return await sessions.preview(db, doc["user_id"], clock_in=body.clock_in, clock_out=body.clock_out, exclude_id=doc["_id"])


@router.patch("/sessions/{session_id}")
async def correct_session(
    session_id: str, body: CorrectionIn, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    doc = await _session(db, session_id)
    updated = await sessions.update_times(
        db, doc, admin, clock_in=body.clock_in, clock_out=body.clock_out, reason=body.reason,
        confirm_overlap=body.confirm_overlap,
    )
    updated = (await _with_volunteers(db, [updated]))[0]
    return {"session": _row(updated, utcnow())}


@router.post("/sessions/{session_id}/mark-reviewed")
async def mark_reviewed(
    session_id: str, body: MarkReviewedIn, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    doc = await _session(db, session_id)
    updated = await sessions.mark_reviewed(db, doc, admin, body.reason)
    updated = (await _with_volunteers(db, [updated]))[0]
    return {"session": _row(updated, utcnow())}


class DeleteIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/sessions/{session_id}/delete")
async def delete_session(
    session_id: str, body: DeleteIn, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    doc = await _session(db, session_id)
    await sessions.delete_session(db, doc, admin, body.reason)
    return {"deleted": str(doc["_id"])}


@router.post("/sessions/{session_id}/restore")
async def restore_session(session_id: str, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await sessions.restore_session(db, parse_oid(session_id, "Session"), admin)
    doc = (await _with_volunteers(db, [doc]))[0]
    return {"session": _row(doc, utcnow())}


@router.get("/audit")
async def audit_log(
    entity_id: str | None = None,
    entity: Literal["seva_session", "user"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    match: dict = {}
    if entity_id:
        match["entity_id"] = parse_oid(entity_id, "Record")
    if entity:
        match["entity"] = entity
    skip, limit = page_params(page, page_size)
    total = await db.audit_logs.count_documents(match)
    logs = await db.audit_logs.find(match).sort([("created_at", -1), ("_id", -1)]).skip(skip).limit(limit).to_list(limit)
    owner_ids = list({x["owner_id"] for x in logs if x.get("owner_id")})
    owners = {u["_id"]: u async for u in db.users.find({"_id": {"$in": owner_ids}}, {"full_name": 1, "username": 1})}
    items = []
    for x in logs:
        owner = owners.get(x.get("owner_id"))
        items.append({**audit_public(x), "owner_name": owner["full_name"] if owner else None,
                      "owner_username": owner["username"] if owner else None})
    return {"items": items, **page_meta(page, page_size, total)}
