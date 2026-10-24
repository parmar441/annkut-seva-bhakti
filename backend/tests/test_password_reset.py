"""Forgot password: organizer-issued, single-use, expiring reset codes."""

from datetime import UTC, datetime

from app.auth.reset import code_digest, new_code, normalize_code
from app.config import get_settings
from app.enums import Role
from tests.conftest import STRONG_PASSWORD

NEW_PASSWORD = "Fresh-Kitchen-Seva-77!"


def _confirm(username, code, password=NEW_PASSWORD, confirm=None):
    return {"username": username, "code": code, "password": password, "confirm_password": confirm or password}


async def _issue(admin_client, user_id):
    r = await admin_client.post(f"/api/admin/users/{user_id}/password-reset")
    assert r.status_code == 201, r.text
    return r.json()["code"]


def test_codes_are_readable_and_normalised():
    code = new_code()
    assert len(code) == 9 and code[4] == "-"
    assert not set(normalize_code(code)) & set("01OIL")
    assert code_digest(code) == code_digest(code.lower().replace("-", " "))


async def test_request_does_not_reveal_whether_username_exists(client, make_user, db):
    await make_user("riya.m")
    known = await client.post("/api/auth/password-reset/request", json={"username": "Riya.M"})
    unknown = await client.post("/api/auth/password-reset/request", json={"username": "nobody-here"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert await db.password_resets.count_documents({}) == 1


async def test_only_one_open_reset_per_user(client, make_user, db):
    await make_user("riya.m")
    for _ in range(3):
        await client.post("/api/auth/password-reset/request", json={"username": "riya.m"})
    assert await db.password_resets.count_documents({"active": True}) == 1


async def test_full_reset_flow_signs_out_old_sessions(admin_client, make_client, make_user, client, db):
    user = await make_user("riya.m")
    async with make_client() as old_device:
        await old_device.login("riya.m")
        await client.post("/api/auth/password-reset/request", json={"username": "riya.m"})

        pending = (await admin_client.get("/api/admin/password-resets")).json()["items"]
        assert [p["volunteer"]["username"] for p in pending] == ["riya.m"] and pending[0]["status"] == "requested"
        listed = (await admin_client.get("/api/admin/users", params={"q": "riya"})).json()["items"][0]
        assert listed["password_reset"] == "requested"

        code = await _issue(admin_client, user["_id"])
        stored = await db.password_resets.find_one({"active": True})
        assert stored["code_hash"] != code and normalize_code(code) not in str(stored)

        r = await client.post("/api/auth/password-reset/confirm", json=_confirm("RIYA.M", code.lower()))
        assert r.status_code == 200, r.text

        # Old password and old sessions no longer work; the new password does.
        assert (await old_device.post("/api/auth/refresh")).status_code == 401
        bad = await client.post("/api/auth/login", json={"username": "riya.m", "password": STRONG_PASSWORD})
        assert bad.status_code == 401
        await client.login("riya.m", NEW_PASSWORD)

    # Single use.
    again = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code, "Another-Seva-Pass-88!"))
    assert again.status_code == 400
    log = (await admin_client.get("/api/admin/audit", params={"entity_id": str(user["_id"])})).json()["items"]
    assert [x["action"] for x in log[:2]] == ["password_reset", "reset_issued"]


async def test_code_is_bound_to_its_username(admin_client, make_user, client):
    riya = await make_user("riya.m")
    await make_user("meeras")
    code = await _issue(admin_client, riya["_id"])
    r = await client.post("/api/auth/password-reset/confirm", json=_confirm("meeras", code))
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_RESET_CODE"


async def test_wrong_codes_lock_the_reset(admin_client, make_user, client):
    user = await make_user("riya.m")
    code = await _issue(admin_client, user["_id"])
    limit = get_settings().reset_code_max_attempts
    for i in range(limit):
        r = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", "AAAA-AAAA"))
        assert r.status_code == (429 if i == limit - 1 else 400)
    r = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code))
    assert r.status_code == 400  # even the right code is dead now


async def test_code_expires(admin_client, make_user, client, clock):
    clock.set(datetime(2026, 10, 24, 15, 0, tzinfo=UTC))
    user = await make_user("riya.m")
    code = await _issue(admin_client, user["_id"])
    clock.advance(minutes=get_settings().reset_code_minutes + 1)
    r = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code))
    assert r.status_code == 400


async def test_new_code_replaces_old_and_cancel_closes(admin_client, make_user, client, db):
    user = await make_user("riya.m")
    first = await _issue(admin_client, user["_id"])
    second = await _issue(admin_client, user["_id"])
    assert await db.password_resets.count_documents({"active": True}) == 1
    assert (await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", first))).status_code == 400
    await admin_client.post(f"/api/admin/users/{user['_id']}/password-reset/cancel")
    assert (await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", second))).status_code == 400


async def test_new_password_must_meet_policy_without_burning_code(admin_client, make_user, client):
    user = await make_user("riya.m")
    code = await _issue(admin_client, user["_id"])
    r = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code, "Password1234!"))
    assert r.status_code == 422 and "too common" in r.json()["error"]["fields"]["password"]
    r = await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code, NEW_PASSWORD, "different"))
    assert r.status_code == 422 and "confirm_password" in r.json()["error"]["fields"]
    assert (await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code))).status_code == 200


async def test_reset_clears_login_lockout(admin_client, make_user, client):
    user = await make_user("riya.m")
    for _ in range(get_settings().login_failures_per_user_ip):
        await client.post("/api/auth/login", json={"username": "riya.m", "password": "Wrong-Password-1!"})
    code = await _issue(admin_client, user["_id"])
    assert (await client.post("/api/auth/password-reset/confirm", json=_confirm("riya.m", code))).status_code == 200
    await client.login("riya.m", NEW_PASSWORD)


async def test_inactive_accounts_cannot_reset(admin_client, make_user, client, db):
    user = await make_user("riya.m")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
    r = await admin_client.post(f"/api/admin/users/{user['_id']}/password-reset")
    assert r.status_code == 409


async def test_volunteers_cannot_issue_codes(user_client, make_user):
    other = await make_user("meeras", role=Role.USER)
    r = await user_client.post(f"/api/admin/users/{other['_id']}/password-reset")
    assert r.status_code == 403
