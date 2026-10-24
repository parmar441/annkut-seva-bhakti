"""Self-service password reset with a security question (no admin involved).

Flow: username -> the account's question -> answer + new password -> done.

- Answers are normalised (case, spacing, punctuation) and stored as Argon2 hashes, like passwords.
- Unknown usernames, and accounts without a question, get a believable question picked from the
  username, so this can't be used to find out which accounts exist.
- RECOVERY_FAILURES_PER_USER wrong answers within RECOVERY_FAILURE_WINDOW_MINUTES pause recovery
  for that username. Per-IP rate limits apply on top.
- A successful reset signs out every device and is audit-logged.
"""

import hashlib
import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, field_validator

from ..audit.service import write_audit
from ..common import utcnow
from ..config import get_settings
from ..enums import SECURITY_QUESTIONS, AuditAction
from ..errors import AppError
from ..ratelimit import limiter
from ..users.service import normalize_username
from .deps import db_dep, get_current_user
from .passwords import (
    DUMMY_HASH,
    hash_password_async,
    normalize_answer,
    password_problems,
    verify_password_async,
)
from .schemas import validate_answer, validate_question
from .throttle import client_ip
from .tokens import revoke_all_for_user

settings = get_settings()


def decoy_question(username_lower: str) -> str:
    """Same question every time for the same unknown username, so probing reveals nothing."""
    key = ("security-question:" + get_settings().jwt_secret).encode()
    n = int.from_bytes(hmac.new(key, username_lower.encode(), hashlib.sha256).digest()[:4], "big")
    return SECURITY_QUESTIONS[n % len(SECURITY_QUESTIONS)]


async def set_security_question(db: AsyncIOMotorDatabase, user: dict, question: str, answer: str) -> None:
    now = utcnow()
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"security_question": question, "security_answer_hash": await hash_password_async(normalize_answer(answer)),
                  "security_set_at": now, "updated_at": now}},
    )
    await write_audit(
        db, entity="user", entity_id=user["_id"], action=AuditAction.UPDATE, actor=user,
        before=None, after={"security_question": question}, reason="Security question set", owner_id=user["_id"],
    )


# ---------- public: forgot password ----------

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


class QuestionIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class AnswerIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)


async def _recent_failures(db: AsyncIOMotorDatabase, username_lower: str) -> int:
    since = utcnow() - timedelta(minutes=settings.recovery_failure_window_minutes)
    return await db.recovery_failures.count_documents({"username": username_lower, "at": {"$gte": since}})


@router.post("/question")
@limiter.limit(settings.reset_request_rate_limit)
async def get_question(request: Request, body: QuestionIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    username = normalize_username(body.username)
    user = await db.users.find_one({"username_lower": username}, {"security_question": 1, "security_answer_hash": 1})
    if user and user.get("security_answer_hash"):
        return {"question": user["security_question"]}
    return {"question": decoy_question(username)}


@router.post("/answer")
@limiter.limit(settings.reset_confirm_rate_limit)
async def reset_with_answer(request: Request, body: AnswerIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    fields: dict[str, str] = {}
    problems = password_problems(body.password, body.username)
    if problems:
        fields["password"] = " ".join(problems)
    if body.password != body.confirm_password:
        fields["confirm_password"] = "Passwords do not match."
    if fields:
        raise AppError(422, "VALIDATION_ERROR", "Please check the highlighted fields.", fields)

    username = normalize_username(body.username)
    if await _recent_failures(db, username) >= settings.recovery_failures_per_user:
        raise AppError(
            429, "TOO_MANY_ATTEMPTS",
            f"Too many wrong answers. Try again in {settings.recovery_failure_window_minutes} minutes, "
            "or ask your Mandal organizer for a reset code.",
        )

    user = await db.users.find_one({"username_lower": username})
    stored = user.get("security_answer_hash") if user else None
    ok = await verify_password_async(normalize_answer(body.answer), stored or DUMMY_HASH)
    if not (ok and stored and user.get("is_active")):
        await db.recovery_failures.insert_one({"username": username, "ip": client_ip(request), "at": utcnow()})
        raise AppError(
            400, "WRONG_ANSWER", "That answer doesn't match. Check the spelling and try again.",
            {"answer": "That answer doesn't match."},
        )

    now = utcnow()
    await db.users.update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": await hash_password_async(body.password), "updated_at": now}}
    )
    await revoke_all_for_user(db, user["_id"])
    await db.recovery_failures.delete_many({"username": username})
    await db.login_failures.delete_many({"username": username})
    # Any organizer-issued code is no longer needed.
    await db.password_resets.update_many(
        {"user_id": user["_id"], "active": True}, {"$set": {"active": False, "status": "cancelled", "closed_at": now}}
    )
    await write_audit(
        db, entity="user", entity_id=user["_id"], action=AuditAction.PASSWORD_RESET, actor=user,
        before=None, after={"password": "changed"}, reason="Password reset with security question", owner_id=user["_id"],
    )
    return {"message": "Your password has been changed. Sign in with your new password."}


# ---------- signed in: set or change the question ----------

me_router = APIRouter(prefix="/api/me", tags=["volunteer"])


class SecurityQuestionIn(BaseModel):
    question: str
    answer: str = Field(min_length=1, max_length=200)
    current_password: str = Field(min_length=1, max_length=256)

    @field_validator("question")
    @classmethod
    def _question(cls, v: str) -> str:
        return validate_question(v)

    @field_validator("answer")
    @classmethod
    def _answer(cls, v: str) -> str:
        return validate_answer(v)


@me_router.get("/security-question")
async def my_question(user: dict = Depends(get_current_user)):
    return {"question": user.get("security_question") if user.get("security_answer_hash") else None}


@me_router.put("/security-question")
async def update_question(
    body: SecurityQuestionIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)
):
    # Re-check the password so a borrowed, signed-in phone can't be used to change recovery.
    if not await verify_password_async(body.current_password, user["password_hash"]):
        raise AppError(400, "WRONG_PASSWORD", "Your current password is incorrect.", {"current_password": "Incorrect password."})
    await set_security_question(db, user, body.question, body.answer)
    return {"question": body.question}
