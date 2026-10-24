from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from .config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def set_database(db: AsyncIOMotorDatabase) -> None:
    """Used by tests to inject an in-memory database."""
    global _db
    _db = db


def is_in_memory() -> bool:
    return get_settings().mongo_url.startswith("mongomock://")


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        s = get_settings()
        if is_in_memory():
            # Dev-only demo mode: data lives in process memory and is lost on restart.
            # Needs requirements-dev.txt. Never use in production.
            from mongomock_motor import AsyncMongoMockClient

            _client = AsyncMongoMockClient(tz_aware=True)
        else:
            _client = AsyncIOMotorClient(
                s.mongo_url,
                tz_aware=True,
                maxPoolSize=s.mongo_max_pool_size,
                serverSelectionTimeoutMS=s.mongo_timeout_ms,
                connectTimeoutMS=s.mongo_timeout_ms,
                socketTimeoutMS=max(s.mongo_timeout_ms * 4, 30000),
                retryWrites=True,
                retryReads=True,
            )
        _db = _client[s.mongo_db]
    return _db


def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_indexes(
        [
            IndexModel([("username_lower", ASCENDING)], unique=True, name="username_lower_unique"),
            IndexModel([("role", ASCENDING), ("is_active", ASCENDING)]),
            IndexModel([("mandal_name", ASCENDING), ("mandal_type", ASCENDING)]),
        ]
    )
    await db.seva_sessions.create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("clock_in", DESCENDING)]),
            IndexModel([("clock_in", ASCENDING)]),
            IndexModel([("mandal_name", ASCENDING), ("mandal_type", ASCENDING), ("clock_in", ASCENDING)]),
            IndexModel([("needs_review", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("clock_in", ASCENDING)]),
        ]
    )
    if not is_in_memory():  # mongomock can't do partial indexes; the service pre-check still applies
        await db.seva_sessions.create_index(
            [("user_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"status": "active"},
            name="one_active_session_per_user",
        )
    await db.audit_logs.create_indexes(
        [
            IndexModel([("entity_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )
    await db.login_failures.create_indexes(
        [
            IndexModel([("username", ASCENDING), ("at", ASCENDING)]),
            # Old failures expire on their own after a day (counting uses the configured window).
            IndexModel([("at", ASCENDING)], expireAfterSeconds=86400, name="at_ttl"),
        ]
    )
    await db.refresh_tokens.create_indexes(
        [
            IndexModel([("token_hash", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="expires_ttl"),
        ]
    )
