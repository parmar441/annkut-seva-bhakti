from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..common import iso, utcnow
from ..enums import AuditAction


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if hasattr(value, "isoformat"):
        return iso(value)
    return value


async def write_audit(
    db: AsyncIOMotorDatabase,
    *,
    entity: str,
    entity_id: ObjectId,
    action: AuditAction,
    actor: dict | None,
    before: dict | None,
    after: dict | None,
    reason: str | None = None,
    owner_id: ObjectId | None = None,
) -> None:
    """Append-only audit record. before/after keep BSON types (dates stay dates)."""
    await db.audit_logs.insert_one(
        {
            "entity": entity,
            "entity_id": entity_id,
            "owner_id": owner_id,
            "action": action.value,
            "actor_id": actor["_id"] if actor else None,
            "actor_role": actor["role"] if actor else "system",
            "actor_username": actor["username"] if actor else None,
            "before": before,
            "after": after,
            "reason": reason,
            "created_at": utcnow(),
        }
    )


def audit_public(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "entity": doc["entity"],
        "entity_id": str(doc["entity_id"]),
        "action": doc["action"],
        "actor_id": str(doc["actor_id"]) if doc.get("actor_id") else None,
        "actor_role": doc.get("actor_role"),
        "actor_username": doc.get("actor_username"),
        "before": _jsonable(doc.get("before")),
        "after": _jsonable(doc.get("after")),
        "reason": doc.get("reason"),
        "created_at": iso(doc["created_at"]),
    }
