"""Admins can delete (archive) a session they don't accept, and undo it."""

from datetime import UTC, datetime

NOW = datetime(2026, 10, 24, 16, 0, tzinfo=UTC)  # Oct 24, noon New York


async def _setup(make_user, make_client, clock):
    clock.set(NOW)
    await make_user("meeras", full_name="Meera Shah")
    async with make_client() as m:
        await m.login("meeras")
        a = (await m.post("/api/me/sessions", json={"clock_in": "2026-10-22T16:00", "clock_out": "2026-10-22T20:30"})).json()["session"]
        b = (await m.post("/api/me/sessions", json={"clock_in": "2026-10-22T19:45", "clock_out": "2026-10-22T21:00",
                                                    "confirm_overlap": True})).json()["session"]
    return a, b


async def test_delete_removes_hours_everywhere_and_is_audited(admin_client, make_user, make_client, clock, db):
    a, b = await _setup(make_user, make_client, clock)
    before = (await admin_client.get("/api/admin/sessions", params={"status": "all"})).json()["totals"]["duration"]["seconds"]
    assert before == 16200 + 4500

    r = await admin_client.post(f"/api/admin/sessions/{b['id']}/delete", json={"reason": "Times not confirmed by coordinator"})
    assert r.status_code == 200, r.text

    report = (await admin_client.get("/api/admin/sessions", params={"status": "all"})).json()
    assert report["total"] == 1 and report["totals"]["duration"]["seconds"] == 16200
    stats = (await admin_client.get("/api/admin/stats")).json()
    assert stats["completed_sessions"] == 1
    assert (await admin_client.get(f"/api/admin/sessions/{b['id']}")).status_code == 404
    assert await db.deleted_sessions.count_documents({}) == 1  # archived, not lost

    log = (await admin_client.get("/api/admin/audit", params={"entity_id": b["id"]})).json()["items"]
    assert log[0]["action"] == "delete" and log[0]["reason"] == "Times not confirmed by coordinator"
    assert log[0]["actor_role"] == "admin" and log[0]["before"]["clock_in"] == "2026-10-22T23:45:00Z"

    async with make_client() as m:
        await m.login("meeras")
        assert (await m.get(f"/api/me/sessions/{b['id']}")).status_code == 404
        summary = (await m.get("/api/me/summary")).json()
        assert summary["totals"]["lifetime"]["duration"]["seconds"] == 16200


async def test_deleting_the_overlap_partner_clears_the_overlap_flag(admin_client, make_user, make_client, clock, db):
    a, b = await _setup(make_user, make_client, clock)
    await admin_client.post(f"/api/admin/sessions/{b['id']}/mark-reviewed", json={})
    # a was not flagged; flag it as overlapping b to check the clean-up.
    from bson import ObjectId

    await db.seva_sessions.update_one(
        {"_id": ObjectId(a["id"])}, {"$set": {"flags": ["overlap"], "overlap_with": [ObjectId(b["id"])], "needs_review": True}}
    )
    await admin_client.post(f"/api/admin/sessions/{b['id']}/delete", json={"reason": "Duplicate entry"})
    left = await db.seva_sessions.find_one({"_id": ObjectId(a["id"])})
    assert left["flags"] == [] and left["overlap_with"] == [] and left["needs_review"] is False


async def test_reason_is_required(admin_client, make_user, make_client, clock):
    a, _ = await _setup(make_user, make_client, clock)
    assert (await admin_client.post(f"/api/admin/sessions/{a['id']}/delete", json={})).status_code == 422
    assert (await admin_client.post(f"/api/admin/sessions/{a['id']}/delete", json={"reason": "   "})).status_code == 422


async def test_undo_restores_the_session(admin_client, make_user, make_client, clock, db):
    a, _ = await _setup(make_user, make_client, clock)
    await admin_client.post(f"/api/admin/sessions/{a['id']}/delete", json={"reason": "Mistake"})
    r = await admin_client.post(f"/api/admin/sessions/{a['id']}/restore")
    assert r.status_code == 200 and r.json()["session"]["duration"]["seconds"] == 16200
    assert await db.deleted_sessions.count_documents({}) == 0
    assert (await admin_client.get("/api/admin/sessions", params={"status": "all"})).json()["total"] == 2
    log = (await admin_client.get("/api/admin/audit", params={"entity_id": a["id"]})).json()["items"]
    assert [x["action"] for x in log[:2]] == ["restore", "delete"]
    assert (await admin_client.post(f"/api/admin/sessions/{a['id']}/restore")).status_code == 404


async def test_restoring_an_active_session_when_a_new_one_exists_is_refused(admin_client, make_client, make_user, clock):
    clock.set(NOW)
    await make_user("riya.m")
    async with make_client() as v:
        await v.login("riya.m")
        first = (await v.post("/api/me/sessions/clock-in")).json()["session"]
        await admin_client.post(f"/api/admin/sessions/{first['id']}/delete", json={"reason": "Clocked in by mistake"})
        assert (await v.post("/api/me/sessions/clock-in")).status_code == 201  # can start fresh
        r = await admin_client.post(f"/api/admin/sessions/{first['id']}/restore")
        assert r.status_code == 409


async def test_volunteers_cannot_delete(user_client, make_user, make_client, clock):
    a, _ = await _setup(make_user, make_client, clock)
    r = await user_client.post(f"/api/admin/sessions/{a['id']}/delete", json={"reason": "x"})
    assert r.status_code == 403
