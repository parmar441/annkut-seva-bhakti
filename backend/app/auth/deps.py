"""Request dependencies: current user and role checks. Every admin route depends on require_admin."""

from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..common import parse_oid
from ..db import get_db
from ..enums import Role
from ..errors import AppError
from .tokens import ACCESS_COOKIE, decode_access_token


def db_dep() -> AsyncIOMotorDatabase:
    return get_db()


async def get_current_user(request: Request, db: AsyncIOMotorDatabase = Depends(db_dep)) -> dict:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise AppError(401, "UNAUTHORIZED", "Please sign in.")
    payload = decode_access_token(token)
    try:
        user_id = parse_oid(payload.get("sub", ""))
    except AppError:
        raise AppError(401, "UNAUTHORIZED", "Please sign in.") from None
    user = await db.users.find_one({"_id": user_id})
    if user is None or not user.get("is_active", False):
        raise AppError(401, "ACCOUNT_INACTIVE", "This account is not active. Contact an organizer.")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    # Role is read from the database, not the token, so a demoted admin loses access immediately.
    if user.get("role") != Role.ADMIN.value:
        raise AppError(403, "FORBIDDEN", "You don't have permission to do that.")
    return user
