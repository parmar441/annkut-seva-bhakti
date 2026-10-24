"""Self-service forgot password with a security question."""

from app.auth.passwords import normalize_answer
from app.auth.recovery import decoy_question, set_security_question
from app.config import get_settings
from app.enums import SECURITY_QUESTIONS
from tests.conftest import STRONG_PASSWORD

Q = "In which city or village were you born?"
NEW = "Fresh-Seva-77!"


def _answer(username, answer, password=NEW, confirm=None):
    return {"username": username, "answer": answer, "password": password, "confirm_password": confirm or password}


async def _with_question(db, make_user, username="riya.m", answer="New Brunswick"):
    user = await make_user(username)
    await set_security_question(db, user, Q, answer)
    return user


def test_answers_ignore_case_spacing_and_punctuation():
    assert normalize_answer("  New   Brunswick! ") == normalize_answer("new brunswick") == "new brunswick"
    assert normalize_answer("St. Mary's") == "st mary s"


async def test_registration_requires_a_listed_question(client):
    base = {"full_name": "Meera Shah", "username": "meeras", "password": STRONG_PASSWORD, "confirm_password": STRONG_PASSWORD,
            "mandal_name": "Edison", "mandal_type": "Yuvti"}
    r = await client.post("/api/auth/register", json=base)
    assert {"security_question", "security_answer"} <= set(r.json()["error"]["fields"])
    r = await client.post("/api/auth/register", json={**base, "security_question": "Favourite colour?", "security_answer": "blue"})
    assert "security_question" in r.json()["error"]["fields"]
    r = await client.post("/api/auth/register", json={**base, "security_question": Q, "security_answer": "a!"})
    assert "security_answer" in r.json()["error"]["fields"]
    r = await client.post("/api/auth/register", json={**base, "security_question": Q, "security_answer": "Edison"})
    assert r.status_code == 201 and r.json()["user"]["has_security_question"] is True


async def test_full_self_service_reset(client, make_client, make_user, db):
    await _with_question(db, make_user)
    async with make_client() as old_device:
        await old_device.login("riya.m")
        r = await client.post("/api/auth/password-reset/question", json={"username": "RIYA.M"})
        assert r.json() == {"question": Q}
        r = await client.post("/api/auth/password-reset/answer", json=_answer("riya.m", "new brunswick"))
        assert r.status_code == 200, r.text
        assert (await old_device.post("/api/auth/refresh")).status_code == 401  # other devices signed out
    assert (await client.post("/api/auth/login", json={"username": "riya.m", "password": STRONG_PASSWORD})).status_code == 401
    await client.login("riya.m", NEW)
    stored = await db.users.find_one({"username_lower": "riya.m"})
    assert "brunswick" not in str(stored).lower()  # answer stored only as a hash


async def test_unknown_usernames_get_a_believable_question(client, make_user, db):
    await make_user("noquestion")  # registered before questions existed
    a = (await client.post("/api/auth/password-reset/question", json={"username": "ghost-user"})).json()
    b = (await client.post("/api/auth/password-reset/question", json={"username": "ghost-user"})).json()
    c = (await client.post("/api/auth/password-reset/question", json={"username": "noquestion"})).json()
    assert a == b == {"question": decoy_question("ghost-user")}
    assert a["question"] in SECURITY_QUESTIONS and c["question"] in SECURITY_QUESTIONS
    r = await client.post("/api/auth/password-reset/answer", json=_answer("ghost-user", "anything"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "WRONG_ANSWER"


async def test_wrong_answers_pause_recovery(client, make_user, db):
    await _with_question(db, make_user)
    for _ in range(get_settings().recovery_failures_per_user):
        r = await client.post("/api/auth/password-reset/answer", json=_answer("riya.m", "Trenton"))
        assert r.status_code == 400
    r = await client.post("/api/auth/password-reset/answer", json=_answer("riya.m", "New Brunswick"))
    assert r.status_code == 429  # even the right answer waits out the pause


async def test_password_rules_checked_before_answer(client, make_user, db):
    await _with_question(db, make_user)
    r = await client.post("/api/auth/password-reset/answer", json=_answer("riya.m", "New Brunswick", "abc"))
    assert r.status_code == 422 and "password" in r.json()["error"]["fields"]
    assert await db.recovery_failures.count_documents({}) == 0


async def test_deactivated_accounts_cannot_self_reset(client, make_user, db):
    user = await _with_question(db, make_user)
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
    r = await client.post("/api/auth/password-reset/answer", json=_answer("riya.m", "New Brunswick"))
    assert r.status_code == 400


async def test_set_question_needs_current_password(user_client):
    me = (await user_client.get("/api/auth/me")).json()["user"]
    assert me["has_security_question"] is False
    body = {"question": Q, "answer": "Edison", "current_password": "Wrong-Pass-1!"}
    assert (await user_client.put("/api/me/security-question", json=body)).status_code == 400
    r = await user_client.put("/api/me/security-question", json={**body, "current_password": STRONG_PASSWORD})
    assert r.status_code == 200
    assert (await user_client.get("/api/me/security-question")).json() == {"question": Q}
    assert (await user_client.get("/api/auth/me")).json()["user"]["has_security_question"] is True
