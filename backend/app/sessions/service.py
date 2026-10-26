"""Seva session rules: clock in/out, manual entry, edits, overlap detection and review flags.

All timestamps are server-side UTC. Durations are always computed here from timestamps.
"""

from datetime import datetime, timedelta

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..audit.service import write_audit
from ..common import iso, utcnow
from ..config import get_settings
from ..enums import AuditAction, Role, SessionFlag, SessionSource, SessionStatus
from ..errors import AppError
from ..reports.timecalc import (
    duration_seconds,
    duration_view,
    ensure_utc,
    intervals_overlap,
    local_date,
    split_by_local_day,
)

# Flags the rules engine recomputes on every change. manual_entry is sticky once set.
_COMPUTED_FLAGS = {SessionFlag.OVERLAP.value, SessionFlag.LONG_SESSION.value, SessionFlag.MISSING_CLOCK_OUT.value}


# ---------- serialization ----------


def display_status(doc: dict) -> str:
    """What the UI shows: active, completed or flagged (needs admin review)."""
    if doc.get("needs_review"):
        return "flagged"
    return doc["status"]


def session_public(doc: dict, now: datetime | None = None) -> dict:
    s = get_settings()
    now = now or utcnow()
    clock_in = ensure_utc(doc["clock_in"])
    clock_out = ensure_utc(doc["clock_out"]) if doc.get("clock_out") else None
    end_for_split = clock_out or now
    split = split_by_local_day(clock_in, end_for_split, s.tz)
    out = {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "mandal_name": doc["mandal_name"],
        "mandal_type": doc["mandal_type"],
        "clock_in": iso(clock_in),
        "clock_out": iso(clock_out),
        "local_date": local_date(clock_in, s.tz).isoformat(),
        "status": doc["status"],
        "display_status": display_status(doc),
        "duration": duration_view(doc.get("duration_seconds")),
        "flags": doc.get("flags", []),
        "needs_review": bool(doc.get("needs_review")),
        "overlap_with": [str(x) for x in doc.get("overlap_with", [])],
        "source": doc.get("source", SessionSource.CLOCK.value),
        "reviewed_at": iso(doc.get("reviewed_at")),
        "crosses_midnight": len(split) > 1,
        "day_split": [{"date": d.isoformat(), **duration_view(secs)} for d, secs in sorted(split.items())]
        if len(split) > 1
        else [],
        "created_at": iso(doc.get("created_at")),
        "updated_at": iso(doc.get("updated_at")),
    }
    if doc["status"] == SessionStatus.ACTIVE.value:
        out["elapsed_seconds"] = max(0, duration_seconds(clock_in, now))
    return out


def _snapshot(doc: dict) -> dict:
    return {
        "clock_in": doc.get("clock_in"),
        "clock_out": doc.get("clock_out"),
        "duration_seconds": doc.get("duration_seconds"),
        "status": doc.get("status"),
        "flags": list(doc.get("flags", [])),
        "needs_review": bool(doc.get("needs_review")),
    }


# ---------- rules ----------


def status_match(status: str | None) -> dict:
    if status == "active":
        return {"status": SessionStatus.ACTIVE.value}
    if status == "completed":
        return {"status": SessionStatus.COMPLETED.value, "needs_review": {"$ne": True}}
    if status == "flagged":
        return {"needs_review": True}
    return {}


def validate_range(clock_in: datetime, clock_out: datetime | None, now: datetime) -> None:
    """Reject impossible ranges. Raises a 422 with per-field messages."""
    s = get_settings()
    fields: dict[str, str] = {}
    if clock_in > now:
        fields["clock_in"] = "Clock-in can't be in the future."
    if clock_out is not None:
        if clock_out > now:
            fields["clock_out"] = "Clock-out can't be in the future."
        elif clock_out <= clock_in:
            fields["clock_out"] = "Clock-out must be after clock-in."
        elif duration_seconds(clock_in, clock_out) > s.max_session_hours * 3600:
            fields["clock_out"] = f"A session can't be longer than {s.max_session_hours:g} hours."
    if fields:
        raise AppError(422, "INVALID_TIME_RANGE", next(iter(fields.values())), fields)


async def find_overlaps(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    start: datetime,
    end: datetime | None,
    now: datetime,
    exclude_id: ObjectId | None = None,
) -> list[dict]:
    """The user's other sessions that overlap [start, end). Open sessions run until now."""
    end = end or now
    query: dict = {"user_id": user_id, "clock_in": {"$lt": end}}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    query["$or"] = [{"clock_out": {"$gt": start}}, {"clock_out": None}]
    found = []
    async for other in db.seva_sessions.find(query).sort("clock_in", 1):
        other_end = other.get("clock_out") or now
        if intervals_overlap(start, end, other["clock_in"], other_end):
            found.append(other)
    return found


def compute_flags(
    existing: list[str],
    *,
    clock_in: datetime,
    clock_out: datetime | None,
    now: datetime,
    overlapping: bool,
    manual: bool,
) -> list[str]:
    s = get_settings()
    flags = {f for f in existing if f not in _COMPUTED_FLAGS}
    if manual:
        flags.add(SessionFlag.MANUAL_ENTRY.value)
    if overlapping:
        flags.add(SessionFlag.OVERLAP.value)
    end = clock_out or now
    if duration_seconds(clock_in, end) > s.long_session_hours * 3600:
        flags.add(SessionFlag.LONG_SESSION.value)
    if clock_out is None and duration_seconds(clock_in, now) > s.missing_clock_out_hours * 3600:
        flags.add(SessionFlag.MISSING_CLOCK_OUT.value)
    # A forgotten clock-out stays visible to admins after the session is closed.
    if clock_out is not None and SessionFlag.MISSING_CLOCK_OUT.value in existing:
        flags.add(SessionFlag.MISSING_CLOCK_OUT.value)
    order = [f.value for f in SessionFlag]
    return sorted(flags, key=order.index)


def _overlap_error(overlaps: list[dict]) -> AppError:
    return AppError(
        409,
        "SESSION_OVERLAP",
        "These times overlap another of your sessions. Adjust the times, or confirm to save and flag it for review.",
        details={"overlaps": [session_public(o) for o in overlaps]},
    )


# ---------- clock in / out ----------


async def get_active_session(db: AsyncIOMotorDatabase, user_id: ObjectId) -> dict | None:
    return await db.seva_sessions.find_one({"user_id": user_id, "status": SessionStatus.ACTIVE.value})


async def clock_in(db: AsyncIOMotorDatabase, user: dict) -> dict:
    existing = await get_active_session(db, user["_id"])
    if existing:
        raise _already_active(existing)
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "mandal_name": user["mandal_name"],
        "mandal_type": user["mandal_type"],
        "clock_in": now,
        "clock_out": None,
        "duration_seconds": None,
        "status": SessionStatus.ACTIVE.value,
        "flags": [],
        "overlap_with": [],
        "needs_review": False,
        "reviewed_by": None,
        "reviewed_at": None,
        "source": SessionSource.CLOCK.value,
        "created_at": now,
        "updated_at": now,
    }
    # No overlap check needed: manual entries can't end in the future, so nothing can cover "now".
    try:
        result = await db.seva_sessions.insert_one(doc)
    except DuplicateKeyError:
        existing = await get_active_session(db, user["_id"])
        raise _already_active(existing) from None
    doc["_id"] = result.inserted_id
    await write_audit(
        db, entity="seva_session", entity_id=doc["_id"], action=AuditAction.CREATE, actor=user,
        before=None, after=_snapshot(doc), reason="Clock in", owner_id=user["_id"],
    )
    return doc


def _already_active(existing: dict | None) -> AppError:
    details = {"session": session_public(existing)} if existing else None
    return AppError(409, "SESSION_ALREADY_ACTIVE", "You're already on seva. End your current session first.", details=details)


async def clock_out(db: AsyncIOMotorDatabase, user: dict) -> dict:
    session = await get_active_session(db, user["_id"])
    if session is None:
        raise AppError(409, "NO_ACTIVE_SESSION", "You don't have an active seva session.")
    now = utcnow()
    secs = duration_seconds(session["clock_in"], now)
    if secs <= 0:
        raise AppError(409, "INVALID_DURATION", "That session is too short to record. Try again in a moment.")
    overlaps = await find_overlaps(db, user["_id"], session["clock_in"], now, now, exclude_id=session["_id"])
    flags = compute_flags(
        session.get("flags", []), clock_in=session["clock_in"], clock_out=now, now=now,
        overlapping=bool(overlaps), manual=False,
    )
    update = {
        "clock_out": now,
        "duration_seconds": secs,
        "status": SessionStatus.COMPLETED.value,
        "flags": flags,
        "overlap_with": [o["_id"] for o in overlaps],
        "needs_review": bool(flags) or bool(session.get("needs_review")),
        "updated_at": now,
    }
    updated = await db.seva_sessions.find_one_and_update(
        {"_id": session["_id"], "status": SessionStatus.ACTIVE.value},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise AppError(409, "NO_ACTIVE_SESSION", "You don't have an active seva session.")
    await write_audit(
        db, entity="seva_session", entity_id=session["_id"], action=AuditAction.UPDATE, actor=user,
        before=_snapshot(session), after=_snapshot(updated), reason="Clock out", owner_id=user["_id"],
    )
    return updated


# ---------- manual entry and edits ----------


async def create_manual(
    db: AsyncIOMotorDatabase, user: dict, *, clock_in: datetime, clock_out: datetime, reason: str | None, confirm_overlap: bool
) -> dict:
    now = utcnow()
    validate_range(clock_in, clock_out, now)
    overlaps = await find_overlaps(db, user["_id"], clock_in, clock_out, now)
    if overlaps and not confirm_overlap:
        raise _overlap_error(overlaps)
    flags = compute_flags([], clock_in=clock_in, clock_out=clock_out, now=now, overlapping=bool(overlaps), manual=True)
    doc = {
        "user_id": user["_id"],
        "mandal_name": user["mandal_name"],
        "mandal_type": user["mandal_type"],
        "clock_in": clock_in,
        "clock_out": clock_out,
        "duration_seconds": duration_seconds(clock_in, clock_out),
        "status": SessionStatus.COMPLETED.value,
        "flags": flags,
        "overlap_with": [o["_id"] for o in overlaps],
        "needs_review": True,
        "reviewed_by": None,
        "reviewed_at": None,
        "source": SessionSource.MANUAL.value,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.seva_sessions.insert_one(doc)
    doc["_id"] = result.inserted_id
    await write_audit(
        db, entity="seva_session", entity_id=doc["_id"], action=AuditAction.CREATE, actor=user,
        before=None, after=_snapshot(doc), reason=(reason or "").strip() or "Manual entry", owner_id=user["_id"],
    )
    return doc


async def update_times(
    db: AsyncIOMotorDatabase,
    session: dict,
    actor: dict,
    *,
    clock_in: datetime | None,
    clock_out: datetime | None,
    reason: str | None,
    confirm_overlap: bool,
) -> dict:
    """Edit a session's times. Users go through this for their own sessions, admins for corrections.

    - A reason is required to edit a completed session, and always for admin corrections.
    - Setting clock_out on an active session completes it ("Add clock-out").
    - User edits are flagged manual_entry and go to the review queue. Admin corrections mark it reviewed.
    """
    is_admin = actor["role"] == Role.ADMIN.value and actor["_id"] != session["user_id"]
    reason = (reason or "").strip()
    was_completed = session["status"] == SessionStatus.COMPLETED.value
    if (was_completed or is_admin) and not reason:
        raise AppError(422, "REASON_REQUIRED", "Please give a reason for this change.", {"reason": "A reason is required."})

    new_in = clock_in or ensure_utc(session["clock_in"])
    old_out = ensure_utc(session["clock_out"]) if session.get("clock_out") else None
    new_out = clock_out or old_out
    if was_completed and new_out is None:
        raise AppError(422, "INVALID_TIME_RANGE", "Clock-out is required.", {"clock_out": "Clock-out is required."})
    if new_in == ensure_utc(session["clock_in"]) and new_out == old_out:
        raise AppError(422, "NO_CHANGES", "Change the clock-in or clock-out time to save.")

    now = utcnow()
    validate_range(new_in, new_out, now)
    overlaps = await find_overlaps(db, session["user_id"], new_in, new_out, now, exclude_id=session["_id"])
    if overlaps and not confirm_overlap:
        raise _overlap_error(overlaps)

    flags = compute_flags(
        session.get("flags", []), clock_in=new_in, clock_out=new_out, now=now,
        overlapping=bool(overlaps), manual=not is_admin,
    )
    update: dict = {
        "clock_in": new_in,
        "clock_out": new_out,
        "flags": flags,
        "overlap_with": [o["_id"] for o in overlaps],
        "updated_at": now,
    }
    if new_out is not None:
        update["duration_seconds"] = duration_seconds(new_in, new_out)
        update["status"] = SessionStatus.COMPLETED.value
    if is_admin:
        update.update(needs_review=False, reviewed_by=actor["_id"], reviewed_at=now)
    else:
        update["needs_review"] = True

    updated = await db.seva_sessions.find_one_and_update(
        {"_id": session["_id"], "updated_at": session["updated_at"]},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise AppError(409, "EDIT_CONFLICT", "This session changed while you were editing. Reload and try again.")
    await write_audit(
        db, entity="seva_session", entity_id=session["_id"],
        action=AuditAction.CORRECT if is_admin else AuditAction.UPDATE, actor=actor,
        before=_snapshot(session), after=_snapshot(updated), reason=reason or "Added clock-out",
        owner_id=session["user_id"],
    )
    return updated


async def mark_reviewed(db: AsyncIOMotorDatabase, session: dict, admin: dict, reason: str | None) -> dict:
    now = utcnow()
    updated = await db.seva_sessions.find_one_and_update(
        {"_id": session["_id"]},
        {"$set": {"needs_review": False, "reviewed_by": admin["_id"], "reviewed_at": now, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    await write_audit(
        db, entity="seva_session", entity_id=session["_id"], action=AuditAction.REVIEW, actor=admin,
        before=_snapshot(session), after=_snapshot(updated), reason=(reason or "").strip() or "Marked reviewed",
        owner_id=session["user_id"],
    )
    return updated


async def preview(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    *,
    clock_in: datetime,
    clock_out: datetime | None,
    exclude_id: ObjectId | None,
) -> dict:
    """Server-calculated duration and warnings for an edit form, without saving anything."""
    now = utcnow()
    errors: dict[str, str] = {}
    try:
        validate_range(clock_in, clock_out, now)
    except AppError as e:
        errors = e.fields or {}
    overlaps = await find_overlaps(db, user_id, clock_in, clock_out, now, exclude_id=exclude_id)
    s = get_settings()
    secs = duration_seconds(clock_in, clock_out) if clock_out else None
    warnings = []
    if secs is not None and secs > s.long_session_hours * 3600 and not errors:
        warnings.append(f"Longer than {s.long_session_hours:g} hours. This session will be flagged for review.")
    tz = s.tz
    split = split_by_local_day(clock_in, clock_out, tz) if clock_out and clock_out > clock_in else {}
    return {
        "clock_in": iso(clock_in),
        "clock_out": iso(clock_out),
        "duration": duration_view(secs) if secs is not None and secs > 0 else None,
        "errors": errors,
        "warnings": warnings,
        "overlaps": [session_public(o, now) for o in overlaps],
        "day_split": [{"date": d.isoformat(), **duration_view(v)} for d, v in sorted(split.items())] if len(split) > 1 else [],
    }


# ---------- admin delete / restore ----------


async def delete_session(db: AsyncIOMotorDatabase, session: dict, admin: dict, reason: str) -> None:
    """Remove a session an organizer doesn't accept. It moves to deleted_sessions (so it can be restored),
    disappears from every list and total, and the deletion is audit-logged."""
    reason = reason.strip()
    if not reason:
        raise AppError(422, "REASON_REQUIRED", "Please give a reason for deleting this session.", {"reason": "A reason is required."})
    now = utcnow()
    archived = {**session, "deleted_at": now, "deleted_by": admin["_id"], "deleted_by_username": admin["username"],
                "delete_reason": reason}
    await db.deleted_sessions.replace_one({"_id": session["_id"]}, archived, upsert=True)
    result = await db.seva_sessions.delete_one({"_id": session["_id"]})
    if result.deleted_count != 1:
        raise AppError(409, "EDIT_CONFLICT", "This session was already removed. Refresh and try again.")

    # Sessions that were flagged only because they overlapped this one are no longer overlapping it.
    async for other in db.seva_sessions.find({"overlap_with": session["_id"]}):
        remaining = [x for x in other.get("overlap_with", []) if x != session["_id"]]
        update: dict = {"overlap_with": remaining}
        if not remaining:
            flags = [f for f in other.get("flags", []) if f != SessionFlag.OVERLAP.value]
            update["flags"] = flags
            if not flags:
                update["needs_review"] = False
        await db.seva_sessions.update_one({"_id": other["_id"]}, {"$set": update})

    await write_audit(
        db, entity="seva_session", entity_id=session["_id"], action=AuditAction.DELETE, actor=admin,
        before=_snapshot(session), after=None, reason=reason, owner_id=session["user_id"],
    )


async def restore_session(db: AsyncIOMotorDatabase, session_id: ObjectId, admin: dict) -> dict:
    archived = await db.deleted_sessions.find_one({"_id": session_id})
    if archived is None:
        raise AppError(404, "NOT_FOUND", "There is no deleted session to restore.")
    doc = {k: v for k, v in archived.items() if k not in ("deleted_at", "deleted_by", "deleted_by_username", "delete_reason")}
    if doc["status"] == SessionStatus.ACTIVE.value and await get_active_session(db, doc["user_id"]):
        raise AppError(409, "SESSION_ALREADY_ACTIVE", "This volunteer has started a new session since. End it before restoring.")
    try:
        await db.seva_sessions.insert_one(doc)
    except DuplicateKeyError:
        raise AppError(409, "SESSION_ALREADY_ACTIVE", "This volunteer has started a new session since. End it before restoring.") from None
    await db.deleted_sessions.delete_one({"_id": session_id})
    await write_audit(
        db, entity="seva_session", entity_id=session_id, action=AuditAction.RESTORE, actor=admin,
        before=None, after=_snapshot(doc), reason="Deletion undone", owner_id=doc["user_id"],
    )
    return doc


# ---------- background sweep ----------


async def sweep_missing_clock_outs(db: AsyncIOMotorDatabase, now: datetime | None = None) -> int:
    """Flag active sessions open longer than MISSING_CLOCK_OUT_HOURS for review."""
    now = now or utcnow()
    cutoff = now - timedelta(hours=get_settings().missing_clock_out_hours)
    result = await db.seva_sessions.update_many(
        {
            "status": SessionStatus.ACTIVE.value,
            "clock_in": {"$lt": cutoff},
            "flags": {"$ne": SessionFlag.MISSING_CLOCK_OUT.value},
        },
        {"$addToSet": {"flags": SessionFlag.MISSING_CLOCK_OUT.value}, "$set": {"needs_review": True}},
    )
    return result.modified_count
