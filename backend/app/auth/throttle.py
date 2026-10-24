"""Per-account brute-force protection for sign-in.

Per-IP rate limits can't stop password guessing without also blocking hundreds of volunteers who
share one event Wi-Fi address. Instead, failed attempts are counted per username+IP (tight) and
per username across all IPs (looser, so an attacker elsewhere can't easily lock someone out).
Counts live in MongoDB so every worker process sees the same numbers.
"""

from datetime import timedelta

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..common import utcnow
from ..config import get_settings
from ..errors import AppError


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def check_login_allowed(db: AsyncIOMotorDatabase, username_lower: str, ip: str) -> int:
    """Raise 429 if this account is locked. Returns recent failures for this username+IP.

    One query (capped at the per-user limit) serves both checks, to keep sign-in cheap under load.
    """
    s = get_settings()
    since = utcnow() - timedelta(minutes=s.login_failure_window_minutes)
    recent = await db.login_failures.find(
        {"username": username_lower, "at": {"$gte": since}}, {"ip": 1, "_id": 0}
    ).to_list(s.login_failures_per_user)
    per_pair = sum(1 for r in recent if r.get("ip") == ip)
    if per_pair >= s.login_failures_per_user_ip or len(recent) >= s.login_failures_per_user:
        raise AppError(
            429,
            "TOO_MANY_ATTEMPTS",
            f"Too many incorrect passwords for this account. Try again in {s.login_failure_window_minutes} minutes "
            "or ask an organizer for help.",
        )
    return per_pair


async def record_login_failure(db: AsyncIOMotorDatabase, username_lower: str, ip: str) -> None:
    await db.login_failures.insert_one({"username": username_lower, "ip": ip, "at": utcnow()})


async def clear_login_failures(db: AsyncIOMotorDatabase, username_lower: str, ip: str) -> None:
    await db.login_failures.delete_many({"username": username_lower, "ip": ip})
