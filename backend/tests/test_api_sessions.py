from datetime import UTC, datetime

from app.enums import Role
from app.sessions.service import sweep_missing_clock_outs

T0 = datetime(2026, 10, 22, 22, 30, tzinfo=UTC)  # Oct 22, 6:30 PM New York


async def test_clock_in_and_out_uses_server_time(user_client, clock, db):
    clock.set(T0)
    r = await user_client.post("/api/me/sessions/clock-in", json={"clock_in": "2020-01-01T00:00:00Z"})
    assert r.status_code == 201, r.text
    s = r.json()["session"]
    assert s["status"] == "active" and s["clock_in"] == "2026-10-22T22:30:00Z"
    assert s["mandal_name"] == "Edison" and s["mandal_type"] == "Yuvti"

    clock.advance(hours=3, minutes=15)
    r = await user_client.post("/api/me/sessions/clock-out", json={"duration_seconds": 1})
    assert r.status_code == 200
    s = r.json()["session"]
    assert s["status"] == "completed"
    assert s["duration"]["seconds"] == 3 * 3600 + 15 * 60
    assert s["duration"]["long"] == "3 hours 15 minutes" and s["duration"]["decimal"] == 3.25
    stored = await db.seva_sessions.find_one({})
    assert await db.audit_logs.count_documents({"entity_id": stored["_id"]}) == 2


async def test_cannot_clock_in_twice(user_client, clock):
    clock.set(T0)
    assert (await user_client.post("/api/me/sessions/clock-in")).status_code == 201
    r = await user_client.post("/api/me/sessions/clock-in")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ACTIVE"


async def test_clock_out_without_active_session(user_client):
    r = await user_client.post("/api/me/sessions/clock-out")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_ACTIVE_SESSION"


async def test_clock_out_zero_duration_rejected(user_client, clock):
    clock.set(T0)
    await user_client.post("/api/me/sessions/clock-in")
    r = await user_client.post("/api/me/sessions/clock-out")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_DURATION"


async def test_mandal_snapshot_survives_profile_change(user_client, clock, db):
    clock.set(T0)
    await user_client.post("/api/me/sessions/clock-in")
    await db.users.update_one({"username_lower": "anjali.p"}, {"$set": {"mandal_name": "Clifton"}})
    clock.advance(hours=1)
    s = (await user_client.post("/api/me/sessions/clock-out")).json()["session"]
    assert s["mandal_name"] == "Edison"


async def test_manual_entry_validation(user_client, clock):
    clock.set(T0)
    bad = [
        ({"clock_in": "2026-10-22T10:00:00", "clock_out": "2026-10-22T09:00:00"}, "clock_out"),
        ({"clock_in": "2026-10-22T10:00:00", "clock_out": "2026-10-23T10:00:00"}, "clock_out"),  # future
        ({"clock_in": "2026-10-20T08:00:00", "clock_out": "2026-10-21T09:00:00"}, "clock_out"),  # > 24h
    ]
    for body, field in bad:
        r = await user_client.post("/api/me/sessions", json=body)
        assert r.status_code == 422, body
        assert field in r.json()["error"]["fields"]


async def test_manual_entry_local_time_and_flags(user_client, clock):
    clock.set(T0)
    r = await user_client.post(
        "/api/me/sessions", json={"clock_in": "2026-10-18T20:15", "clock_out": "2026-10-19T00:45", "reason": "Forgot"}
    )
    assert r.status_code == 201, r.text
    s = r.json()["session"]
    assert s["clock_in"] == "2026-10-19T00:15:00Z"  # 8:15 PM EDT
    assert s["flags"] == ["manual_entry"] and s["display_status"] == "flagged"
    assert s["crosses_midnight"] is True
    assert [d["seconds"] for d in s["day_split"]] == [13500, 2700]


async def test_long_manual_entry_is_flagged(user_client, clock):
    clock.set(T0)
    r = await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-21T04:00", "clock_out": "2026-10-21T21:00"})
    assert r.status_code == 201
    assert "long_session" in r.json()["session"]["flags"]


async def test_overlap_rejected_then_allowed_with_confirmation(user_client, clock):
    clock.set(T0)
    first = {"clock_in": "2026-10-21T16:00", "clock_out": "2026-10-21T20:30"}
    assert (await user_client.post("/api/me/sessions", json=first)).status_code == 201
    second = {"clock_in": "2026-10-21T19:45", "clock_out": "2026-10-21T21:00"}
    r = await user_client.post("/api/me/sessions", json=second)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SESSION_OVERLAP" and len(err["details"]["overlaps"]) == 1

    r = await user_client.post("/api/me/sessions", json={**second, "confirm_overlap": True})
    assert r.status_code == 201
    s = r.json()["session"]
    assert "overlap" in s["flags"] and s["needs_review"] and len(s["overlap_with"]) == 1


async def test_adjacent_sessions_do_not_overlap(user_client, clock):
    clock.set(T0)
    assert (await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-21T09:00", "clock_out": "2026-10-21T12:00"})).status_code == 201
    r = await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-21T12:00", "clock_out": "2026-10-21T13:00"})
    assert r.status_code == 201
    assert "overlap" not in r.json()["session"]["flags"]


async def test_manual_entry_overlapping_active_session(user_client, clock):
    clock.set(T0)
    await user_client.post("/api/me/sessions/clock-in")
    clock.advance(hours=2)
    r = await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-22T19:00", "clock_out": "2026-10-22T19:30"})
    assert r.status_code == 409


async def test_edit_completed_requires_reason_and_is_audited(user_client, clock, db):
    clock.set(T0)
    await user_client.post("/api/me/sessions/clock-in")
    clock.advance(hours=2, minutes=45)
    sid = (await user_client.post("/api/me/sessions/clock-out")).json()["session"]["id"]
    clock.advance(minutes=47)  # 10:02 PM, as in the mockup

    r = await user_client.patch(f"/api/me/sessions/{sid}", json={"clock_out": "2026-10-22T21:45"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "REASON_REQUIRED"

    r = await user_client.patch(f"/api/me/sessions/{sid}", json={"clock_out": "2026-10-22T21:45", "reason": "Stayed for clean-up"})
    assert r.status_code == 200, r.text
    s = r.json()["session"]
    assert s["duration"]["seconds"] == 3 * 3600 + 15 * 60
    assert "manual_entry" in s["flags"] and s["needs_review"]

    audit = (await user_client.get(f"/api/me/sessions/{sid}/audit")).json()["items"]
    assert audit[0]["action"] == "update" and audit[0]["reason"] == "Stayed for clean-up"
    assert audit[0]["before"]["clock_out"] == "2026-10-23T01:15:00Z"
    assert audit[0]["after"]["clock_out"] == "2026-10-23T01:45:00Z"
    assert audit[0]["actor_username"] == "anjali.p"


async def test_add_clock_out_to_active_session(user_client, clock):
    clock.set(T0)
    sid = (await user_client.post("/api/me/sessions/clock-in")).json()["session"]["id"]
    clock.advance(hours=20)
    r = await user_client.patch(f"/api/me/sessions/{sid}", json={"clock_out": "2026-10-22T21:30"})
    assert r.status_code == 200, r.text
    s = r.json()["session"]
    assert s["status"] == "completed" and s["duration"]["seconds"] == 3 * 3600
    # Now the volunteer can start a new session.
    assert (await user_client.post("/api/me/sessions/clock-in")).status_code == 201


async def test_missing_clock_out_sweep(user_client, clock, db):
    clock.set(T0)
    await user_client.post("/api/me/sessions/clock-in")
    clock.advance(hours=13)
    assert await sweep_missing_clock_outs(db) == 1
    s = await db.seva_sessions.find_one({})
    assert s["flags"] == ["missing_clock_out"] and s["needs_review"] is True
    assert await sweep_missing_clock_outs(db) == 0


async def test_users_cannot_see_or_edit_others_sessions(make_client, make_user, clock):
    clock.set(T0)
    await make_user("usera")
    await make_user("userb")
    async with make_client() as a, make_client() as b:
        await a.login("usera")
        await b.login("userb")
        sid = (await a.post("/api/me/sessions", json={"clock_in": "2026-10-21T09:00", "clock_out": "2026-10-21T10:00"})).json()["session"]["id"]
        assert (await b.get(f"/api/me/sessions/{sid}")).status_code == 404
        assert (await b.patch(f"/api/me/sessions/{sid}", json={"clock_out": "2026-10-21T11:00", "reason": "x"})).status_code == 404
        assert (await b.get(f"/api/me/sessions/{sid}/audit")).status_code == 404
        assert (await b.post("/api/me/sessions/preview", json={"clock_in": "2026-10-21T09:00", "session_id": sid})).status_code == 404
        assert (await b.get("/api/me/sessions")).json()["total"] == 0
        assert (await b.get("/api/me/sessions/not-an-id")).status_code == 404
        assert (await a.get(f"/api/me/sessions/{sid}")).status_code == 200


async def test_summary_and_totals_split_midnight(user_client, clock):
    clock.set(datetime(2026, 10, 19, 16, 0, tzinfo=UTC))  # Oct 19 noon NY
    await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-18T20:15", "clock_out": "2026-10-19T00:45"})
    await user_client.post("/api/me/sessions/clock-in")
    clock.advance(minutes=30)

    summary = (await user_client.get("/api/me/summary")).json()
    assert summary["totals"]["today"]["duration"]["seconds"] == 2700 + 1800  # 45m after midnight + live 30m
    assert summary["totals"]["lifetime"]["duration"]["seconds"] == 16200 + 1800
    assert summary["active_session"]["elapsed_seconds"] == 1800
    assert len(summary["recent"]) == 2

    totals = (await user_client.get("/api/me/totals", params={"from": "2026-10-18", "to": "2026-10-18"})).json()
    assert totals["duration"]["seconds"] == 13500
    days = (await user_client.get("/api/me/totals", params={"from": "2026-10-18", "to": "2026-10-19", "group": "day"})).json()
    assert [(b["start"], b["seconds"]) for b in days["buckets"]] == [("2026-10-18", 13500), ("2026-10-19", 4500)]


async def test_history_list_filters_and_range_total(user_client, clock):
    clock.set(T0)
    for cin, cout in [("2026-10-01T09:00", "2026-10-01T10:00"), ("2026-10-15T09:00", "2026-10-15T11:00"), ("2026-09-30T23:00", "2026-10-01T01:00")]:
        assert (await user_client.post("/api/me/sessions", json={"clock_in": cin, "clock_out": cout})).status_code == 201
    r = (await user_client.get("/api/me/sessions", params={"from": "2026-10-01", "to": "2026-10-31"})).json()
    assert r["total"] == 3
    assert r["summary"]["duration"]["seconds"] == 3600 + 7200 + 3600  # Sept 30 part clipped off
    r = (await user_client.get("/api/me/sessions", params={"from": "2026-10-10", "to": "2026-10-20"})).json()
    assert r["total"] == 1


async def test_preview_returns_server_duration_and_overlaps(user_client, clock):
    clock.set(T0)
    await user_client.post("/api/me/sessions", json={"clock_in": "2026-10-21T21:30", "clock_out": "2026-10-21T22:15"})
    r = await user_client.post("/api/me/sessions/preview", json={"clock_in": "2026-10-21T18:30", "clock_out": "2026-10-21T22:15"})
    body = r.json()
    assert body["duration"]["long"] == "3 hours 45 minutes" and body["duration"]["decimal"] == 3.75
    assert len(body["overlaps"]) == 1 and body["errors"] == {}


async def test_nonexistent_dst_time_rejected(user_client, clock):
    clock.set(datetime(2026, 3, 10, tzinfo=UTC))
    r = await user_client.post("/api/me/sessions", json={"clock_in": "2026-03-08T02:30", "clock_out": "2026-03-08T05:00"})
    assert r.status_code == 422
    assert "clock_in" in r.json()["error"]["fields"]


async def test_admin_can_use_volunteer_endpoints_for_own_sessions(make_client, make_user, clock):
    clock.set(T0)
    await make_user("boss", role=Role.ADMIN)
    async with make_client() as c:
        await c.login("boss")
        assert (await c.post("/api/me/sessions/clock-in")).status_code == 201
