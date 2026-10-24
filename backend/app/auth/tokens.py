"""JWT access tokens, rotating refresh tokens and the auth cookies."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from bson import ObjectId
from fastapi import Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import get_settings
from ..errors import AppError

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
REFRESH_PATH = "/api/auth"


def utcnow() -> datetime:
    # Real wall clock for token lifetimes, independent of the (test-freezable) seva clock.
    return datetime.now(UTC).replace(microsecond=0)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user: dict) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user["_id"]),
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Your session has expired. Please sign in again.") from None
    except jwt.InvalidTokenError:
        raise AppError(401, "UNAUTHORIZED", "Please sign in.") from None
    if payload.get("type") != "access":
        raise AppError(401, "UNAUTHORIZED", "Please sign in.")
    return payload


async def issue_refresh_token(db: AsyncIOMotorDatabase, user_id: ObjectId, request: Request) -> str:
    s = get_settings()
    token = secrets.token_urlsafe(48)
    now = utcnow()
    await db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": _hash_token(token),
            "expires_at": now + timedelta(days=s.refresh_token_days),
            "revoked_at": None,
            "created_at": now,
            "user_agent": (request.headers.get("user-agent") or "")[:300],
            "ip": request.client.host if request.client else None,
        }
    )
    return token


async def rotate_refresh_token(db: AsyncIOMotorDatabase, token: str) -> dict:
    """Revoke the presented token and return its record. Reuse of a revoked token revokes the whole family."""
    record = await db.refresh_tokens.find_one({"token_hash": _hash_token(token)})
    now = utcnow()
    if record is None:
        raise AppError(401, "UNAUTHORIZED", "Please sign in again.")
    if record.get("revoked_at") is not None:
        # Token replay: someone is using an old token. Revoke every token for this user.
        await revoke_all_for_user(db, record["user_id"])
        raise AppError(401, "UNAUTHORIZED", "Please sign in again.")
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=now.tzinfo)
    if expires_at <= now:
        raise AppError(401, "UNAUTHORIZED", "Your session has expired. Please sign in again.")
    result = await db.refresh_tokens.update_one(
        {"_id": record["_id"], "revoked_at": None}, {"$set": {"revoked_at": now}}
    )
    if result.modified_count != 1:
        await revoke_all_for_user(db, record["user_id"])
        raise AppError(401, "UNAUTHORIZED", "Please sign in again.")
    return record


async def revoke_token(db: AsyncIOMotorDatabase, token: str) -> None:
    await db.refresh_tokens.update_one(
        {"token_hash": _hash_token(token), "revoked_at": None}, {"$set": {"revoked_at": utcnow()}}
    )


async def revoke_all_for_user(db: AsyncIOMotorDatabase, user_id: ObjectId) -> None:
    await db.refresh_tokens.update_many({"user_id": user_id, "revoked_at": None}, {"$set": {"revoked_at": utcnow()}})


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_kwargs() -> dict:
    s = get_settings()
    return {"secure": s.cookie_secure, "samesite": s.cookie_samesite, "domain": s.cookie_domain}


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    kw = _cookie_kwargs()
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=s.access_token_minutes * 60, httponly=True, path="/", **kw
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, max_age=s.refresh_token_days * 86400, httponly=True, path=REFRESH_PATH, **kw
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    s = get_settings()
    # Readable by JS on purpose: the client echoes it in the X-CSRF-Token header (double submit).
    response.set_cookie(CSRF_COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=False, path="/", **_cookie_kwargs())


def clear_auth_cookies(response: Response) -> None:
    kw = _cookie_kwargs()
    response.delete_cookie(ACCESS_COOKIE, path="/", **kw)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, **kw)
