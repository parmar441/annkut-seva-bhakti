"""Load sample data for local development: one admin, volunteers in every Mandal, and ~60 days of sessions.

Usage:
    python -m app.scripts.seed            # adds sample data (skips if volunteers already exist)
    python -m app.scripts.seed --reset    # wipes users, sessions, audit logs and tokens first

All sample accounts use the password in SEED_PASSWORD (default: Seva-Demo-2026!).
Refuses to run when ENVIRONMENT=production.
"""

import argparse
import asyncio
import os
import random
import sys
from datetime import UTC, datetime, time, timedelta

from ..auth.passwords import hash_password
from ..common import utcnow
from ..config import get_settings
from ..db import close_db, ensure_indexes, get_db
from ..enums import MANDAL_NAMES, MANDAL_TYPES, Role, SessionFlag
from ..reports.timecalc import duration_seconds, local_date

VOLUNTEERS = [
    ("Anjali Patel", "anjali.p"), ("Meera Shah", "meeras"), ("Kavita Desai", "kdesai"), ("Riya Mehta", "riya.m"),
    ("Nisha Joshi", "nisha"), ("Pooja Trivedi", "pooja.t"), ("Hetal Amin", "hetal.a"), ("Krupa Bhatt", "krupa"),
    ("Dhara Modi", "dhara.m"), ("Jinal Parikh", "jinal.p"), ("Komal Thakkar", "komal.t"), ("Mansi Vyas", "mansi"),
    ("Shreya Pandya", "shreya.p"), ("Foram Gandhi", "foram.g"), ("Bhavna Raval", "bhavna"), ("Ekta Dave", "ekta.d"),
    ("Payal Soni", "payal.s"), ("Rina Chauhan", "rina.c"), ("Tanvi Kapadia", "tanvi.k"), ("Urvi Sheth", "urvi.s"),
]


async def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reset", action="store_true")
    p.add_argument("--days", type=int, default=60)
    args = p.parse_args(argv)

    if get_settings().environment == "production":
        sys.exit("Refusing to seed a production database.")
    db = get_db()
    if args.reset:
        for c in ("users", "seva_sessions", "audit_logs", "refresh_tokens"):
            await db[c].delete_many({})
    await ensure_indexes(db)
    if await db.users.count_documents({"role": Role.USER.value}):
        sys.exit("Volunteers already exist. Re-run with --reset to start over.")
    counts = await seed_database(db, days=args.days)
    print(f"Seeded 1 admin, {counts['volunteers']} volunteers and {counts['sessions']} sessions.")
    print("Sign in as 'organizer' (admin) or 'anjali.p' (volunteer). Password: SEED_PASSWORD or Seva-Demo-2026!")
    close_db()


async def seed_database(db, days: int = 60) -> dict:
    """Insert sample data into an empty database. Returns counts."""
    s = get_settings()
    rng = random.Random(108)
    password_hash = hash_password(os.environ.get("SEED_PASSWORD", "Seva-Demo-2026!"))
    now = utcnow()
    tz = s.tz

    def user_doc(full_name, username, mandal, mtype, role):
        return {
            "full_name": full_name, "username": username, "username_lower": username.lower(),
            "password_hash": password_hash, "mandal_name": mandal, "mandal_type": mtype, "role": role,
            "is_active": True, "created_at": now - timedelta(days=days + 5), "updated_at": now, "last_login_at": None,
        }

    admin = user_doc("Edison Organizer", "organizer", "Edison", "Yuvti", Role.ADMIN.value)
    await db.users.insert_one(admin)

    users = []
    for i, (name, username) in enumerate(VOLUNTEERS):
        doc = user_doc(name, username, MANDAL_NAMES[i % len(MANDAL_NAMES)], MANDAL_TYPES[(i // 2) % len(MANDAL_TYPES)], Role.USER.value)
        if username == "anjali.p":
            doc.update(mandal_name="Edison", mandal_type="Yuvti")
        if username == "nisha":
            doc["is_active"] = False
        await db.users.insert_one(doc)
        users.append(doc)

    sessions = []
    today = local_date(now, tz)
    for u in users:
        for back in range(days, 0, -1):
            if rng.random() > 0.3:
                continue
            day = today - timedelta(days=back)
            if u["username"] == "meeras" and back == 1:
                continue  # leave room for the deliberate overlap example below
            start_hour = rng.choice([9, 10, 16, 17, 18, 20])
            start = datetime.combine(day, time(start_hour, rng.choice([0, 15, 30, 45])), tzinfo=tz).astimezone(UTC)
            end = start + timedelta(minutes=rng.choice([90, 120, 150, 180, 195, 210, 240, 270]))
            if end > now:
                continue
            sessions.append(_session(u, start, end, now))

    # Review-queue examples
    by_name = {u["username"]: u for u in users}
    s1 = now - timedelta(hours=40)
    sessions.append(_session(by_name["riya.m"], s1, None, now, flags=[SessionFlag.MISSING_CLOCK_OUT.value]))
    base = datetime.combine(today - timedelta(days=1), time(16, 0), tzinfo=tz).astimezone(UTC)
    a = _session(by_name["meeras"], base, base + timedelta(hours=4, minutes=30), now)
    b = _session(by_name["meeras"], base + timedelta(hours=3, minutes=45), base + timedelta(hours=5), now,
                 flags=[SessionFlag.OVERLAP.value, SessionFlag.MANUAL_ENTRY.value], source="manual")
    sessions += [a, b]
    # Active session for the demo volunteer
    sessions.append(_session(by_name["anjali.p"], now - timedelta(hours=2, minutes=18), None, now))

    # Drop random sessions that overlap earlier ones for the same user, except the deliberate examples.
    sessions.sort(key=lambda d: (d["user_id"], d["clock_in"]))
    kept, last_end = [], {}
    for d in sessions:
        end = d["clock_out"] or now
        prev = last_end.get(d["user_id"])
        if prev and d["clock_in"] < prev and d is not a and SessionFlag.OVERLAP.value not in d["flags"]:
            continue
        kept.append(d)
        last_end[d["user_id"]] = max(prev or end, end)
    result = await db.seva_sessions.insert_many(kept)
    await db.seva_sessions.update_one({"_id": b["_id"]}, {"$set": {"overlap_with": [a["_id"]]}})
    return {"volunteers": len(users), "sessions": len(result.inserted_ids)}


def _session(user, start, end, now, flags=None, source="clock"):
    flags = list(flags or [])
    return {
        "user_id": user["_id"], "mandal_name": user["mandal_name"], "mandal_type": user["mandal_type"],
        "clock_in": start, "clock_out": end, "duration_seconds": duration_seconds(start, end) if end else None,
        "status": "completed" if end else "active", "flags": flags, "overlap_with": [],
        "needs_review": bool(flags), "reviewed_by": None, "reviewed_at": None, "source": source,
        "created_at": start, "updated_at": end or start,
    }


if __name__ == "__main__":
    asyncio.run(main())
