"""Milestone 1 (Flash-Next's plan): records and booking (US1), through the back office's routes."""
import random
from datetime import date, timedelta

from conftest import FRI, MON, NEXT_MON, SAT, TUE, assert_no_overlaps, cleaners_of, slot


def test_cleaner_crud(app):
    c = app.post("/cleaners", {"name": "  Ana  "})
    assert c["name"] == "Ana" and isinstance(c["id"], int)             # trimmed
    assert app.get(f"/cleaners/{c['id']}") == c
    assert app.post(f"/cleaners/{c['id']}", {"name": "Ana B"})["name"] == "Ana B"
    assert [x["name"] for x in app.get("/cleaners")] == ["Ana B"]
    app.post(f"/cleaners/{c['id']}/delete")
    app.fails("GET", f"/cleaners/{c['id']}", codes=("not_found",))


def test_client_crud(app):
    c = app.post("/clients", {"name": "Home 1"})
    assert app.get(f"/clients/{c['id']}") == c
    assert app.post(f"/clients/{c['id']}", {"name": "Home 2"})["name"] == "Home 2"
    app.post(f"/clients/{c['id']}/delete")
    app.fails("GET", f"/clients/{c['id']}", codes=("not_found",))


def test_bad_input_changes_nothing(app):
    app.cleaners(2)
    cl = app.client()
    before = app.state()
    app.fails("POST", "/cleaners", {"name": "   "}, codes=("invalid_input",))
    app.fails("POST", "/clients", {"name": ""}, codes=("invalid_input",))
    app.fails("GET", "/cleaners/9999", codes=("not_found",))
    app.fails("POST", "/jobs/book", {"client_id": 9999, "cleaners_required": 1, "hours": 1, "requested_day": MON}, codes=("not_found",))
    app.fails("POST", "/jobs/book", {"client_id": cl, "cleaners_required": 1, "hours": 1, "requested_day": "15/11/2027"}, codes=("invalid_input",))
    assert app.state() == before


def test_first_booking(app):
    ids = app.cleaners(12)
    j = app.book(app.client(), 2, 4, MON)
    assert (j["booked_start"], j["booked_end"], j["state"]) == (f"{MON}T08:00", f"{MON}T12:00", "scheduled")
    assert cleaners_of(j) == ids[:2] and j["expected_length_min"] == 240 and j["cleaners_required"] == 2
    assert app.get(f"/jobs/{j['id']}") == j


def test_one_hour_gap(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 4, MON)                        # 8:00-12:00
    assert app.book(cl, 1, 2, MON)["booked_start"] == f"{MON}T13:00"


def test_earliest_start_to_the_minute(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 4.25, MON)                     # 8:00-12:15
    assert app.book(cl, 1, 1, MON)["booked_start"] == f"{MON}T13:15"


def test_weekends_and_full_days(app):
    app.cleaners(1)
    cl = app.client()
    assert slot(app.book(cl, 1, 1, SAT)) == (NEXT_MON, 480)              # a Saturday request: the Monday after
    full = app.book(cl, 1, 9, FRI)
    assert (full["booked_start"], full["booked_end"]) == (f"{FRI}T08:00", f"{FRI}T17:00")
    assert slot(app.book(cl, 1, 1, FRI)) == (NEXT_MON, 600)              # Friday full; Monday 8-9 taken: 10:00


def test_a_job_must_end_by_five(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 5, MON)                        # 8:00-13:00
    assert slot(app.book(cl, 1, 4, MON)) == (TUE, 480)


def test_refusals(app):
    app.cleaners(2)
    cl = app.client()
    before = app.state()
    app.fails("POST", "/jobs/book", {"client_id": cl, "cleaners_required": 1, "hours": 9.25, "requested_day": MON}, codes=("job_too_long",))
    for n, h in ((1, 0), (1, -1), (0, 1), (4, 1)):
        app.fails("POST", "/jobs/book", {"client_id": cl, "cleaners_required": n, "hours": h, "requested_day": MON}, codes=("invalid_input",))
    app.fails("POST", "/jobs/book", {"client_id": cl, "cleaners_required": 3, "hours": 1, "requested_day": MON}, codes=("no_feasible_slot",))
    assert app.state() == before


def test_several_cleaners_need_a_common_start(app):
    a, b, c = app.cleaners(3)
    cl = app.client()
    app.book(cl, 2, 4, MON)                        # a, b 8:00-12:00
    j = app.book(cl, 2, 2, MON)                    # only c free at 8:00
    assert (slot(j), cleaners_of(j)) == ((MON, 780), [a, b])


def test_job_edit_rebooks_and_delete_removes(app):
    app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 4, MON)                   # 8:00-12:00
    j2 = app.book(cl, 1, 2, MON)                   # 13:00-15:00
    e = app.post(f"/jobs/{j2['id']}", {"client_id": cl, "cleaners_required": 1, "hours": 5, "requested_day": MON})
    assert (e["expected_length_min"], slot(e)) == (300, (TUE, 480))   # 13:00 + 5 h passes 17:00
    app.post(f"/jobs/{j1['id']}/delete")
    app.fails("GET", f"/jobs/{j1['id']}", codes=("not_found",))
    assert app.book(cl, 1, 1, MON)["booked_start"] == f"{MON}T08:00"


def test_data_survives_a_restart(app):
    app.cleaners(3)
    app.book(app.client(), 2, 3.5, MON)
    before = app.state()
    app.restart()
    assert app.state() == before


def test_pages_answer(app):
    status, page = app.call("GET", "/", json_answer=False)
    assert status == 200 and "<html" in page.lower()
    assert app.call("GET", "/cleaners", json_answer=False)[0] == 200


def oracle(jobs, ids, n, mins, requested):
    """A minute-by-minute scan of the booking rule (research D-3): earliest weekday start, lowest-id cleaners."""
    d = date.fromisoformat(requested)
    while True:
        if d.weekday() < 5:
            day = d.isoformat()
            busy = [(cleaners_of(j), *slot(j)[1:], slot(j)[1] + j["expected_length_min"]) for j in jobs
                    if j["state"] == "scheduled" and slot(j)[0] == day]
            for s in range(480, 1020 - mins + 1):
                ok = [c for c in ids if all(c not in cs or js >= s + mins + 60 or s >= je + 60 for cs, js, je in busy)]
                if len(ok) >= n:
                    return (day, s), ok[:n]
        d += timedelta(days=1)


def test_random_workload_matches_the_rule(app):
    rnd = random.Random(20271115)
    ids = app.cleaners(12)
    cls = [app.client(f"Client {i}") for i in range(5)]
    for _ in range(60):
        n = rnd.choice((1, 1, 2, 3))
        quarters = max(2, min(36, int(rnd.gauss(16.5, 7))))   # ~4.14 h +- 1.75 h, in quarter hours
        req = (date(2027, 11, 15) + timedelta(days=rnd.randrange(10))).isoformat()
        want = oracle(app.get("/jobs"), ids, n, quarters * 15, req)
        j = app.book(rnd.choice(cls), n, quarters / 4, req)
        assert (slot(j), cleaners_of(j)) == want, (n, quarters, req)
    assert_no_overlaps(app.get("/jobs"))
