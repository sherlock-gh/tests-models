"""Milestone 1 (Terra's plan): records, booking, the server and its page (US1)."""
import random
from datetime import date, timedelta

from conftest import MON, NEXT_MON, SAT, TUE, assert_no_overlaps, by_id

FRI = "2026-11-20"


def test_cleaner_crud(app):
    c = app.ok("POST", "/api/cleaners", {"name": "Ana"})
    assert c["name"] == "Ana" and isinstance(c["id"], int)
    assert app.ok("GET", f"/api/cleaners/{c['id']}") == c
    assert app.ok("PUT", f"/api/cleaners/{c['id']}", {"name": "Ana B"})["name"] == "Ana B"
    assert [x["name"] for x in app.ok("GET", "/api/cleaners")] == ["Ana B"]
    app.ok("DELETE", f"/api/cleaners/{c['id']}")
    app.fails("GET", f"/api/cleaners/{c['id']}", code="not_found", status=404)
    assert app.ok("GET", "/api/cleaners") == []


def test_client_crud(app):
    c = app.ok("POST", "/api/clients", {"name": "Home 1"})
    assert c["name"] == "Home 1"
    assert app.ok("GET", f"/api/clients/{c['id']}") == c
    assert app.ok("PUT", f"/api/clients/{c['id']}", {"name": "Home 2"})["name"] == "Home 2"
    app.ok("DELETE", f"/api/clients/{c['id']}")
    app.fails("GET", f"/api/clients/{c['id']}", code="not_found", status=404)


def test_bad_input_changes_nothing(app):
    app.cleaners(2)
    cl = app.client()
    before = app.state()
    app.fails("POST", "/api/cleaners", {"name": "  "}, code="invalid_input", status=400)
    app.fails("POST", "/api/clients", {"name": ""}, code="invalid_input", status=400)
    app.fails("GET", "/api/cleaners/9999", code="not_found", status=404)
    app.fails("PUT", "/api/clients/9999", {"name": "x"}, code="not_found", status=404)
    app.fails("POST", "/api/jobs", {"clientId": 9999, "cleanersNeeded": 1, "durationMinutes": 60, "requestedDate": MON}, code=("not_found", "invalid_input"))
    app.fails("POST", "/api/jobs", {"clientId": cl, "cleanersNeeded": 1, "durationMinutes": 60, "requestedDate": "not a date"}, code="invalid_input")
    assert app.state() == before


def test_c1_first_booking(app):
    ids = app.cleaners(12)
    j = app.book(app.client(), 2, 240, MON)
    assert (j["date"], j["startMinute"], j["endMinute"]) == (MON, 480, 720)
    assert j["cleanerIds"] == sorted(ids)[:2] and j["status"] == "scheduled"
    assert j["requestedDate"] == MON and j["durationMinutes"] == 240 and j["cleanersNeeded"] == 2
    assert app.ok("GET", f"/api/jobs/{j['id']}") == j


def test_c2_one_hour_gap(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 240, MON)                      # 8:00-12:00
    j = app.book(cl, 1, 120, MON)
    assert (j["date"], j["startMinute"]) == (MON, 780)   # 13:00, exactly an hour later


def test_earliest_slot_is_not_on_a_grid(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 247, MON)                      # ends 12:07
    assert app.book(cl, 1, 60, MON)["startMinute"] == 787   # 13:07


def test_c3_c5_weekends_and_full_days(app):
    app.cleaners(1)
    cl = app.client()
    assert app.book(cl, 1, 60, SAT)["date"] == NEXT_MON        # a Saturday request: the Monday after
    full = app.book(cl, 1, 540, FRI)
    assert (full["date"], full["startMinute"], full["endMinute"]) == (FRI, 480, 1020)   # C4: 9 h fills a day
    nxt = app.book(cl, 1, 60, FRI)
    assert (nxt["date"], nxt["startMinute"]) == (NEXT_MON, 600)  # Friday full, the weekend skipped; Monday 8-9 taken: 10:00


def test_slot_must_end_by_five(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 300, MON)                      # 8:00-13:00
    j = app.book(cl, 1, 240, MON)                  # 14:00-18:00 would pass 17:00
    assert (j["date"], j["startMinute"]) == (TUE, 480)


def test_c4_c6_refusals(app):
    app.cleaners(2)
    cl = app.client()
    before = app.state()
    for n, length in ((1, 541), (1, 0), (1, -5), (0, 60), (4, 60)):
        app.fails("POST", "/api/jobs", {"clientId": cl, "cleanersNeeded": n, "durationMinutes": length, "requestedDate": MON},
                  code="invalid_input", status=400)
    app.fails("POST", "/api/jobs", {"clientId": cl, "cleanersNeeded": 3, "durationMinutes": 60, "requestedDate": MON},
              code=("unschedulable", "invalid_input"))
    assert app.state() == before


def test_several_cleaners_need_a_common_start(app):
    a, b, c = sorted(app.cleaners(3))
    cl = app.client()
    app.book(cl, 2, 240, MON)                      # a, b: 8:00-12:00
    j = app.book(cl, 2, 120, MON)                  # only c is free at 8:00
    assert (j["startMinute"], j["cleanerIds"]) == (780, [a, b])


def test_job_update_rebooks_and_delete(app):
    app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)
    j2 = app.book(cl, 1, 120, MON)                 # 13:00
    u = app.ok("PUT", f"/api/jobs/{j2['id']}", {"requestedDate": TUE})
    assert (u["date"], u["startMinute"], u["requestedDate"]) == (TUE, 480, TUE)
    app.ok("DELETE", f"/api/jobs/{j1['id']}")
    st, out = app.call("GET", f"/api/jobs/{j1['id']}")   # deleted: gone, or kept as cancelled (the plan doesn't say which)
    assert st == 404 or (st == 200 and out["status"] == "cancelled"), (st, out)
    assert app.book(cl, 1, 60, MON)["startMinute"] == 480


def test_data_survives_a_restart(app):
    app.cleaners(3)
    app.book(app.client(), 2, 200, MON)
    before = app.state()
    app.restart()
    assert app.state() == before
    assert app.data.exists()


def test_page_and_bad_requests(app):
    status, body = app.call("GET", "/")
    assert status == 200 and "<html" in str(body).lower()
    app.cleaners(1)
    st, _ = app.call("POST", "/api/cleaners", None)        # no body
    assert 400 <= st < 500
    assert app.call("GET", "/api/cleaners")[0] == 200


def oracle(jobs, cleaner_ids, needed, length, requested):
    """Per-minute scan of the booking rule: the earliest (date, start) and its lowest-id free cleaners."""
    d = date.fromisoformat(requested)
    while True:
        if d.weekday() < 5:
            day = d.isoformat()
            busy = [j for j in jobs if j["status"] != "cancelled" and j["date"] == day]
            for s in range(480, 1020 - length + 1):
                ok = [c for c in sorted(cleaner_ids)
                      if all(j["endMinute"] + 60 <= s or j["startMinute"] >= s + length + 60 for j in busy if c in j["cleanerIds"])]
                if len(ok) >= needed:
                    return day, s, ok[:needed]
        d += timedelta(days=1)


def test_random_workload_matches_the_rule(app):
    rnd = random.Random(20261116)
    ids = app.cleaners(12)
    cls = [app.client(f"Client {i}") for i in range(5)]
    for _ in range(70):
        needed = rnd.choice((1, 1, 2, 3))
        length = max(30, min(540, int(rnd.gauss(248, 105))))
        req = (date(2026, 11, 16) + timedelta(days=rnd.randrange(10))).isoformat()
        expect = oracle(app.ok("GET", "/api/jobs"), ids, needed, length, req)
        j = app.book(rnd.choice(cls), needed, length, req)
        assert (j["date"], j["startMinute"], j["cleanerIds"]) == expect, (needed, length, req)
    assert_no_overlaps(app.ok("GET", "/api/jobs"))
