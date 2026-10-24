from fastapi import APIRouter, Depends, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..audit.service import write_audit
from ..common import utcnow
from ..config import get_settings
from ..enums import AuditAction, Role
from ..errors import AppError
from ..ratelimit import limiter
from ..users.service import create_user, normalize_username, user_public
from .deps import db_dep, get_current_user
from .passwords import DUMMY_HASH, hash_password_async, is_pwned, needs_rehash, password_problems, verify_password_async
from .throttle import check_login_allowed, clear_login_failures, client_ip, record_login_failure
from .schemas import LoginIn, RegisterIn
from .tokens import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_access_token,
    issue_refresh_token,
    new_csrf_token,
    revoke_token,
    rotate_refresh_token,
    set_auth_cookies,
    set_csrf_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


async def _start_session(db: AsyncIOMotorDatabase, user: dict, request: Request, response: Response) -> None:
    refresh = await issue_refresh_token(db, user["_id"], request)
    set_auth_cookies(response, create_access_token(user), refresh)
    set_csrf_cookie(response, new_csrf_token())


@router.get("/csrf", summary="Issue a CSRF token cookie (call before the first POST)")
async def csrf(request: Request, response: Response):
    token = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    set_csrf_cookie(response, token)
    return {"csrf_token": token}


@router.post("/register", status_code=201)
@limiter.limit(settings.register_rate_limit)
async def register(request: Request, response: Response, body: RegisterIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    fields: dict[str, str] = {}
    problems = password_problems(body.password, body.username)
    if not problems and settings.hibp_enabled and await is_pwned(body.password):
        problems.append("This password has appeared in a data breach. Choose a different one.")
    if problems:
        fields["password"] = " ".join(problems)
    if body.password != body.confirm_password:
        fields["confirm_password"] = "Passwords do not match."
    if fields:
        raise AppError(422, "VALIDATION_ERROR", "Please check the highlighted fields.", fields)

    # Self-registration always creates a General User. There is no way to request another role.
    user = await create_user(
        db,
        full_name=body.full_name,
        username=body.username,
        password=body.password,
        mandal_name=body.mandal_name.value,
        mandal_type=body.mandal_type.value,
        role=Role.USER,
        security_question=body.security_question,
        security_answer=body.security_answer,
    )
    await write_audit(
        db, entity="user", entity_id=user["_id"], action=AuditAction.CREATE, actor=user,
        before=None, after={"username": user["username"], "role": user["role"]}, reason="Self-registration",
    )
    return {"user": user_public(user)}


@router.post("/login")
@limiter.limit(settings.login_rate_limit)
async def login(request: Request, response: Response, body: LoginIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    username = normalize_username(body.username)
    ip = client_ip(request)
    prior_failures = await check_login_allowed(db, username, ip)
    user = await db.users.find_one({"username_lower": username})
    invalid = AppError(401, "INVALID_CREDENTIALS", "Incorrect username or password.")
    if user is None:
        await verify_password_async(body.password, DUMMY_HASH)
        await record_login_failure(db, username, ip)
        raise invalid
    if not await verify_password_async(body.password, user["password_hash"]):
        await record_login_failure(db, username, ip)
        raise invalid
    if prior_failures:
        await clear_login_failures(db, username, ip)
    if not user.get("is_active", False):
        raise AppError(403, "ACCOUNT_INACTIVE", "This account has been deactivated. Contact an organizer.")

    updates = {"last_login_at": utcnow()}
    if needs_rehash(user["password_hash"]):
        updates["password_hash"] = await hash_password_async(body.password)
    await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
    user.update(updates)

    await _start_session(db, user, request, response)
    return {"user": user_public(user)}


@router.post("/refresh")
@limiter.limit(settings.refresh_rate_limit)
async def refresh(request: Request, response: Response, db: AsyncIOMotorDatabase = Depends(db_dep)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise AppError(401, "UNAUTHORIZED", "Please sign in.")
    record = await rotate_refresh_token(db, token)
    user = await db.users.find_one({"_id": record["user_id"]})
    if user is None or not user.get("is_active", False):
        clear_auth_cookies(response)
        raise AppError(401, "ACCOUNT_INACTIVE", "This account is not active. Contact an organizer.")
    await _start_session(db, user, request, response)
    return {"user": user_public(user)}


@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncIOMotorDatabase = Depends(db_dep)):
    response = Response(status_code=204)
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await revoke_token(db, token)
    clear_auth_cookies(response)
    return response


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user_public(user)}
