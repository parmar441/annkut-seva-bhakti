"""Load and failure behaviour: brute-force lockout, parallel sign-ins, DB outages, unexpected errors."""

import asyncio

import httpx
from limits import parse_many
from pymongo.errors import ServerSelectionTimeoutError

from app.config import get_settings
from tests.conftest import BASE_URL, STRONG_PASSWORD, ApiClient


async def _login(c, username, password=STRONG_PASSWORD):
    return await c.post("/api/auth/login", json={"username": username, "password": password})


def test_rate_limit_strings_are_valid_and_event_sized():
    s = get_settings()
    for value in (s.login_rate_limit, s.register_rate_limit, s.refresh_rate_limit, s.api_rate_limit):
        assert parse_many(value)
    # 500 volunteers on one Wi-Fi address must be able to sign in within a minute.
    assert parse_many(s.login_rate_limit)[0].amount >= 500


async def test_500_parallel_logins_all_succeed(make_client, db):
    from app.auth.passwords import hash_password

    pw_hash = hash_password(STRONG_PASSWORD)
    from app.common import utcnow

    now = utcnow()
    await db.users.insert_many(
        [
            {"full_name": f"Volunteer {i}", "username": f"vol{i}", "username_lower": f"vol{i}", "password_hash": pw_hash,
             "mandal_name": "Edison", "mandal_type": "Yuvti", "role": "user", "is_active": True,
             "created_at": now, "updated_at": now, "last_login_at": None}
            for i in range(500)
        ]
    )
    clients = [make_client() for _ in range(500)]
    results = await asyncio.gather(*(_login(c, f"vol{i}") for i, c in enumerate(clients)))
    assert [r.status_code for r in results].count(200) == 500
    assert await db.refresh_tokens.count_documents({}) == 500
    for c in clients:
        await c.aclose()


async def test_failed_logins_lock_the_account_for_that_ip(client, make_user, make_client):
    await make_user("riya.m")
    for _ in range(get_settings().login_failures_per_user_ip):
        assert (await _login(client, "riya.m", "Wrong-Password-1!")).status_code == 401
    r = await _login(client, "riya.m")  # even the right password is refused during the lockout
    assert r.status_code == 429 and r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

    await make_user("meeras")
    assert (await _login(client, "meeras")).status_code == 200  # other accounts unaffected


async def test_successful_login_clears_failures(client, make_user, db):
    await make_user("riya.m")
    for _ in range(get_settings().login_failures_per_user_ip - 1):
        await _login(client, "riya.m", "Wrong-Password-1!")
    assert (await _login(client, "riya.m")).status_code == 200
    assert await db.login_failures.count_documents({"username": "riya.m"}) == 0


async def test_database_outage_returns_503(client, db, monkeypatch):
    async def boom(*a, **kw):
        raise ServerSelectionTimeoutError("cluster unreachable")

    monkeypatch.setattr(type(db.users), "find_one", boom)
    r = await _login(client, "anyone")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert r.headers["Retry-After"] == "5"


async def test_unexpected_error_returns_json_500(app, monkeypatch):
    from app.auth import router as auth_router

    def broken(*a, **kw):
        raise RuntimeError("bug")

    monkeypatch.setattr(auth_router, "normalize_username", broken)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with ApiClient(transport=transport, base_url=BASE_URL) as c:
        r = await _login(c, "anyone")
    assert r.status_code == 500
    body = r.json()["error"]
    assert body["code"] == "INTERNAL_ERROR" and "bug" not in body["message"]
    assert body["details"]["request_id"]


async def test_health_endpoints(client):
    assert (await client.get("/api/health")).json() == {"status": "ok"}
    assert (await client.get("/api/health/ready")).json()["database"] == "ok"
