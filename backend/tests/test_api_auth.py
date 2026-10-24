from app.enums import Role
from tests.conftest import STRONG_PASSWORD

REG = {
    "full_name": "Meera Shah",
    "username": "MeeraS",
    "password": STRONG_PASSWORD,
    "confirm_password": STRONG_PASSWORD,
    "mandal_name": "Jersey City",
    "mandal_type": "Kishori",
}


async def test_register_then_login(client, db):
    r = await client.post("/api/auth/register", json=REG)
    assert r.status_code == 201, r.text
    user = r.json()["user"]
    assert user["role"] == "user" and user["mandal_name"] == "Jersey City"
    stored = await db.users.find_one({"username_lower": "meeras"})
    assert stored["password_hash"].startswith("$argon2id$")

    r = await client.post("/api/auth/login", json={"username": "meeras", "password": STRONG_PASSWORD})
    assert r.status_code == 200
    assert "access_token" in client.cookies and "refresh_token" in client.cookies
    me = await client.get("/api/auth/me")
    assert me.json()["user"]["username"] == "MeeraS"


async def test_cannot_self_register_as_admin(client, db):
    r = await client.post("/api/auth/register", json={**REG, "role": "admin"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "user"
    assert (await db.users.find_one({"username_lower": "meeras"}))["role"] == "user"


async def test_username_unique_case_insensitive(client):
    assert (await client.post("/api/auth/register", json=REG)).status_code == 201
    r = await client.post("/api/auth/register", json={**REG, "username": "meeras"})
    assert r.status_code == 409
    assert r.json()["error"]["fields"]["username"]


async def test_register_field_errors(client):
    r = await client.post(
        "/api/auth/register",
        json={**REG, "password": "weakpassword", "confirm_password": "different", "mandal_name": "Nowhere"},
    )
    assert r.status_code == 422
    fields = r.json()["error"]["fields"]
    assert "mandal_name" in fields


async def test_register_password_rules_and_mismatch(client):
    r = await client.post("/api/auth/register", json={**REG, "password": "Password1234!", "confirm_password": "nope"})
    assert r.status_code == 422
    fields = r.json()["error"]["fields"]
    assert "too common" in fields["password"]
    assert fields["confirm_password"] == "Passwords do not match."


async def test_register_requires_all_fields(client):
    r = await client.post("/api/auth/register", json={"username": "x"})
    assert r.status_code == 422
    fields = r.json()["error"]["fields"]
    for f in ("full_name", "password", "confirm_password", "mandal_name", "mandal_type"):
        assert f in fields


async def test_login_wrong_password(client, make_user):
    await make_user("riya.m")
    r = await client.post("/api/auth/login", json={"username": "riya.m", "password": "Wrong-Password-1!"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = await client.post("/api/auth/login", json={"username": "nobody", "password": "Wrong-Password-1!"})
    assert r.status_code == 401


async def test_csrf_required_for_mutations(client, make_user):
    await make_user("riya.m")
    r = await client.post(
        "/api/auth/login", json={"username": "riya.m", "password": STRONG_PASSWORD}, headers={"X-CSRF-Token": "bogus"}
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"


async def test_csrf_rejects_foreign_origin(client, make_user):
    await make_user("riya.m")
    await client.csrf()
    r = await client.post(
        "/api/auth/login",
        json={"username": "riya.m", "password": STRONG_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


async def test_protected_routes_need_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/me/summary")).status_code == 401
    assert (await client.post("/api/me/sessions/clock-in")).status_code == 401


async def test_refresh_rotates_and_detects_reuse(client, make_user, db):
    await make_user("riya.m")
    await client.login("riya.m")
    old_refresh = client.cookies.get("refresh_token")

    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the old token fails and revokes the whole family, including the new one.
    client.cookies.set("refresh_token", old_refresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401
    assert await db.refresh_tokens.count_documents({"revoked_at": None}) == 0


async def test_refresh_tokens_stored_hashed(client, make_user, db):
    await make_user("riya.m")
    await client.login("riya.m")
    raw = client.cookies.get("refresh_token")
    rec = await db.refresh_tokens.find_one({})
    assert rec["token_hash"] != raw and len(rec["token_hash"]) == 64


async def test_logout_revokes_refresh(client, make_user, db):
    await make_user("riya.m")
    await client.login("riya.m")
    r = await client.post("/api/auth/logout")
    assert r.status_code == 204
    assert await db.refresh_tokens.count_documents({"revoked_at": None}) == 0
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_deactivated_user_cannot_login_or_refresh(make_client, make_user, db):
    user = await make_user("riya.m")
    async with make_client() as c:
        await c.login("riya.m")
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
        assert (await c.post("/api/auth/refresh")).status_code == 401
        assert (await c.get("/api/auth/me")).status_code == 401
        r = await c.post("/api/auth/login", json={"username": "riya.m", "password": STRONG_PASSWORD})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "ACCOUNT_INACTIVE"


async def test_admin_role_comes_from_database(make_client, make_user, db):
    admin = await make_user("boss", role=Role.ADMIN)
    async with make_client() as c:
        await c.login("boss")
        assert (await c.get("/api/admin/stats")).status_code == 200
        await db.users.update_one({"_id": admin["_id"]}, {"$set": {"role": "user"}})
        assert (await c.get("/api/admin/stats")).status_code == 403


async def test_tampered_token_rejected(client, make_user):
    await make_user("riya.m")
    await client.login("riya.m")
    token = client.cookies.get("access_token")
    header, payload, sig = token.split(".")
    client.cookies.set("access_token", f"{header}.{payload}.{sig[:-4]}abcd")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_meta_enums(client):
    r = await client.get("/api/meta/enums")
    body = r.json()
    assert body["mandal_names"] == ["Edison", "Jersey City", "Clifton", "Parsippany", "Passaic", "Pennsylvania"]
    assert body["mandal_types"] == ["Kishori", "Yuvti", "Sahid", "Sahradayi"]
    assert body["timezone"] == "America/New_York"
