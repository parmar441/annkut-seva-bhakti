from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..auth.passwords import hash_password_async, normalize_answer
from ..common import iso, utcnow
from ..enums import Role
from ..errors import AppError


def normalize_username(username: str) -> str:
    return username.strip().lower()


def user_public(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "full_name": user["full_name"],
        "username": user["username"],
        "mandal_name": user["mandal_name"],
        "mandal_type": user["mandal_type"],
        "role": user["role"],
        "is_active": user["is_active"],
        "has_security_question": bool(user.get("security_answer_hash")),
        "created_at": iso(user.get("created_at")),
        "last_login_at": iso(user.get("last_login_at")),
    }


async def create_user(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    username: str,
    password: str,
    mandal_name: str,
    mandal_type: str,
    role: Role = Role.USER,
    security_question: str | None = None,
    security_answer: str | None = None,
) -> dict:
    now = utcnow()
    doc = {
        "full_name": full_name.strip(),
        "username": username.strip(),
        "username_lower": normalize_username(username),
        "password_hash": await hash_password_async(password),
        "mandal_name": mandal_name,
        "mandal_type": mandal_type,
        "role": role.value,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    if security_question and security_answer:
        doc["security_question"] = security_question
        doc["security_answer_hash"] = await hash_password_async(normalize_answer(security_answer))
        doc["security_set_at"] = now
    if await db.users.find_one({"username_lower": doc["username_lower"]}, {"_id": 1}):
        raise AppError(409, "USERNAME_TAKEN", "That username is taken.", {"username": "That username is already taken."})
    try:
        result = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise AppError(409, "USERNAME_TAKEN", "That username is taken.", {"username": "That username is already taken."}) from None
    doc["_id"] = result.inserted_id
    return doc


async def get_user(db: AsyncIOMotorDatabase, user_id: ObjectId) -> dict | None:
    return await db.users.find_one({"_id": user_id})
