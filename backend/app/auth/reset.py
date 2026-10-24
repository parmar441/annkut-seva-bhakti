"""Forgotten passwords: organizer-issued one-time reset codes.

There is no email on file, so identity is checked in person:
1. The volunteer asks for a reset with their (unique) username. The response is identical whether
   or not the username exists, so this can't be used to discover accounts.
2. An organizer verifies them and issues a code. Each user has at most one open reset (unique
   partial index), a code works once, expires after RESET_CODE_MINUTES and is invalidated after
   RESET_CODE_MAX_ATTEMPTS wrong tries. Only an HMAC of the code is stored.
3. The volunteer enters username + code + new password. All their sessions are signed out.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..audit.service import write_audit
from ..common import iso, page_meta, page_params, parse_oid, utcnow
from ..config import get_settings
from ..enums import AuditAction
from ..errors import AppError, not_found
from ..ratelimit import limiter
from ..users.service import normalize_username
from .deps import db_dep, require_admin
from .passwords import hash_password_async, password_problems
from .throttle import client_ip
from .tokens import revoke_all_for_user

settings = get_settings()

# No 0/O, 1/I/L: codes are read out loud or copied from a screen.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LEN = 8

INVALID_CODE = AppError(
    400, "INVALID_RESET_CODE", "That username and code don't match an active reset. Check both, or ask an organizer for a new code.",
    {"code": "Invalid or expired code."},
)


def new_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def code_digest(code: str) -> str:
    key = hashlib.sha256(("password-reset:" + get_settings().jwt_secret).encode()).digest()
    return hmac.new(key, normalize_code(code).encode(), hashlib.sha256).hexdigest()


def _expired(reset: dict, now) -> bool:
    exp = reset.get("expires_at")
    if exp is None:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=now.tzinfo)
    return exp <= now


async def open_reset(db: AsyncIOMotorDatabase, user_id) -> dict | None:
    """The user's single open reset, closing it first if its code has expired."""
    now = utcnow()
    reset = await db.password_resets.find_one({"user_id": user_id, "active": True})
    if reset and reset["status"] == "issued" and _expired(reset, now):
        await db.password_resets.update_one(
            {"_id": reset["_id"], "active": True}, {"$set": {"active": False, "status": "expired", "closed_at": now}}
        )
        return None
    return reset


def reset_public(reset: dict, user: dict | None = None) -> dict:
    out = {
        "id": str(reset["_id"]),
        "user_id": str(reset["user_id"]),
        "status": reset["status"],
        "requested_at": iso(reset.get("requested_at")),
        "issued_at": iso(reset.get("issued_at")),
        "expires_at": iso(reset.get("expires_at")),
        "issued_by": reset.get("issued_by_username"),
        "attempts": reset.get("attempts", 0),
    }
    if user:
        out["volunteer"] = {
            "id": str(user["_id"]), "full_name": user["full_name"], "username": user["username"],
            "mandal_name": user["mandal_name"], "mandal_type": user["mandal_type"], "is_active": user["is_active"],
        }
    return out


# ---------- public (volunteer) ----------

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


class ResetRequestIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ResetConfirmIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)


@router.post("/request", status_code=202)
@limiter.limit(settings.reset_request_rate_limit)
async def request_reset(request: Request, body: ResetRequestIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await db.users.find_one({"username_lower": normalize_username(body.username)}, {"_id": 1, "is_active": 1})
    if user and user.get("is_active"):
        now = utcnow()
        existing = await open_reset(db, user["_id"])
        if existing:
            # Keep a code that was already issued; just note the new request.
            await db.password_resets.update_one(
                {"_id": existing["_id"]}, {"$set": {"requested_at": now, "requested_ip": client_ip(request)}}
            )
        else:
            try:
                await db.password_resets.insert_one(
                    {"user_id": user["_id"], "active": True, "status": "requested", "requested_at": now,
                     "requested_ip": client_ip(request), "code_hash": None, "attempts": 0, "created_at": now}
                )
            except DuplicateKeyError:
                pass  # a parallel request already opened one
    return {
        "message": "If that username exists, your request has been sent to the organizers. "
        "Ask your Mandal organizer for your reset code."
    }


@router.post("/confirm")
@limiter.limit(settings.reset_confirm_rate_limit)
async def confirm_reset(request: Request, body: ResetConfirmIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    fields: dict[str, str] = {}
    problems = password_problems(body.password, body.username)
    if problems:
        fields["password"] = " ".join(problems)
    if body.password != body.confirm_password:
        fields["confirm_password"] = "Passwords do not match."
    if fields:
        raise AppError(422, "VALIDATION_ERROR", "Please check the highlighted fields.", fields)

    digest = code_digest(body.code)
    user = await db.users.find_one({"username_lower": normalize_username(body.username)})
    reset = await open_reset(db, user["_id"]) if user else None
    if not user or not user.get("is_active") or not reset or reset["status"] != "issued":
        hmac.compare_digest(digest, digest)  # keep timing similar for unknown users
        raise INVALID_CODE

    if not hmac.compare_digest(digest, reset.get("code_hash") or ""):
        attempts = reset.get("attempts", 0) + 1
        update: dict = {"attempts": attempts}
        if attempts >= settings.reset_code_max_attempts:
            update.update(active=False, status="locked", closed_at=utcnow())
        await db.password_resets.update_one({"_id": reset["_id"]}, {"$set": update})
        if attempts >= settings.reset_code_max_attempts:
            raise AppError(
                429, "RESET_CODE_LOCKED", "Too many wrong codes. Ask an organizer for a new code.",
                {"code": "This code is no longer valid."},
            )
        raise INVALID_CODE

    now = utcnow()
    # Atomic single use: only one request can flip this reset from issued to used.
    used = await db.password_resets.find_one_and_update(
        {"_id": reset["_id"], "active": True, "status": "issued"},
        {"$set": {"active": False, "status": "used", "used_at": now, "closed_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if used is None:
        raise INVALID_CODE

    await db.users.update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": await hash_password_async(body.password), "updated_at": now}}
    )
    await revoke_all_for_user(db, user["_id"])
    await db.login_failures.delete_many({"username": user["username_lower"]})
    await write_audit(
        db, entity="user", entity_id=user["_id"], action=AuditAction.PASSWORD_RESET, actor=user,
        before=None, after={"password": "changed"}, reason="Password reset with organizer code", owner_id=user["_id"],
    )
    return {"message": "Your password has been changed. Sign in with your new password."}


# ---------- admin ----------

admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@admin_router.get("/password-resets")
async def list_resets(
    status: str = Query("open", pattern="^(open|requested|issued)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    match: dict = {"active": True}
    if status != "open":
        match["status"] = status
    skip, limit = page_params(page, page_size)
    docs = await db.password_resets.find(match).sort("requested_at", -1).skip(skip).limit(limit).to_list(limit)
    now = utcnow()
    live = [d for d in docs if not (d["status"] == "issued" and _expired(d, now))]
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": [d["user_id"] for d in live]}}, {"password_hash": 0})}
    total = await db.password_resets.count_documents(match)
    return {"items": [reset_public(d, users.get(d["user_id"])) for d in live], **page_meta(page, page_size, total)}


@admin_router.get("/users/{user_id}/password-reset")
async def get_user_reset(user_id: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")}, {"_id": 1})
    if user is None:
        raise not_found("Volunteer")
    reset = await open_reset(db, user["_id"])
    return {"reset": reset_public(reset) if reset else None}


@admin_router.post("/users/{user_id}/password-reset", status_code=201)
async def issue_code(user_id: str, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Issue a new one-time code (replacing any earlier code). The plain code is returned only here."""
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")})
    if user is None:
        raise not_found("Volunteer")
    if not user.get("is_active"):
        raise AppError(409, "ACCOUNT_INACTIVE", "Activate this account before resetting its password.")
    now = utcnow()
    code = new_code()
    fields = {
        "status": "issued", "code_hash": code_digest(code), "attempts": 0, "issued_at": now,
        "expires_at": now + timedelta(minutes=settings.reset_code_minutes),
        "issued_by": admin["_id"], "issued_by_username": admin["username"],
    }
    existing = await open_reset(db, user["_id"])
    if existing:
        reset = await db.password_resets.find_one_and_update(
            {"_id": existing["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER
        )
    else:
        doc = {"user_id": user["_id"], "active": True, "requested_at": None, "created_at": now, **fields}
        try:
            doc["_id"] = (await db.password_resets.insert_one(doc)).inserted_id
            reset = doc
        except DuplicateKeyError:
            raise AppError(409, "RESET_IN_PROGRESS", "Another organizer just issued a code. Refresh and try again.") from None
    await write_audit(
        db, entity="user", entity_id=user["_id"], action=AuditAction.RESET_ISSUED, actor=admin,
        before=None, after={"expires_at": fields["expires_at"]}, reason="Password reset code issued", owner_id=user["_id"],
    )
    return {"code": code, "reset": reset_public(reset, user)}


@admin_router.post("/users/{user_id}/password-reset/cancel")
async def cancel_reset(user_id: str, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await db.users.find_one({"_id": parse_oid(user_id, "Volunteer")}, {"_id": 1})
    if user is None:
        raise not_found("Volunteer")
    await db.password_resets.update_many(
        {"user_id": user["_id"], "active": True},
        {"$set": {"active": False, "status": "cancelled", "closed_at": utcnow(), "cancelled_by": admin["_id"]}},
    )
    return {"reset": None}
