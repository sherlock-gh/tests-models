"""Milestone 3: extensions and the rebooking they cause (plan US5; C13-C15)."""
import random
from datetime import date, timedelta

from conftest import MON, TUE, assert_no_overlaps


def ext(app, job, cleaner, minutes):
    return app.ok("POST", f"/api/jobs/{job['id']}/extend", {"cleanerId": cleaner, "minutes": minutes})


def test_c13_extension_moves_the_next_job(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)                 # 8:00-12:00
    j2 = app.book(cl, 1, 240, MON)                 # 13:00-17:00
    x = ext(app, j1, a, 20)
    assert x["endMinute"] == 740
    k = app.ok("GET", f"/api/jobs/{j2['id']}")     # 13:20 + 4 h passes 17:00: Tuesday
    assert (k["date"], k["startMinute"], k["endMinute"], k["cleanerIds"]) == (TUE, 480, 720, [a])


def test_moved_job_starts_an_hour_after_the_new_end(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    app.book(cl, 1, 240, MON)                      # a 8:00-12:00
    j1 = app.book(cl, 1, 240, MON)                 # b 8:00-12:00
    j2 = app.book(cl, 1, 120, MON)                 # a 13:00-15:00
    first = app.ok("GET", "/api/jobs")[0]          # the first job: a
    assert first["cleanerIds"] == [a] and j2["cleanerIds"] == [a] and j2["startMinute"] == 780
    ext(app, first, a, 40)                         # a now ends 12:40
    k = app.ok("GET", f"/api/jobs/{j2['id']}")
    assert (k["date"], k["startMinute"]) == (MON, 820)   # 13:40, the earliest start allowed
    assert app.ok("GET", f"/api/jobs/{j1['id']}")["startMinute"] == 480


def test_a_full_hour_left_moves_nothing(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    x = app.book(cl, 1, 240, MON)                  # a 8:00-12:00
    app.book(cl, 1, 260, MON)                      # b 8:00-12:20
    z = app.book(cl, 2, 120, MON)                  # a and b 13:20-15:20
    assert (x["cleanerIds"], z["startMinute"], z["cleanerIds"]) == ([a], 800, [a, b])
    ext(app, x, a, 20)                             # a ends 12:20: exactly an hour before 13:20
    assert app.ok("GET", f"/api/jobs/{z['id']}")["startMinute"] == 800
    ext(app, x, a, 20)                             # a ends 12:40: z must start 13:40 or later
    k = app.ok("GET", f"/api/jobs/{z['id']}")
    assert (k["date"], k["startMinute"], k["cleanerIds"]) == (MON, 820, [a, b])


def test_c14_c15_amounts_and_late_ends(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j = app.book(cl, 1, 540, MON)                  # 8:00-17:00
    before = app.state()
    for m in (30, 0, -20, 15):
        app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": a, "minutes": m}, code="invalid_input")
    assert app.state() == before
    assert ext(app, j, a, 40)["endMinute"] == 1060   # past 17:00 is allowed
    assert ext(app, j, a, 60)["endMinute"] == 1120


def test_extension_refusals(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    j = app.book(cl, 1, 120, MON)
    app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": b, "minutes": 20})       # b is not on it
    app.fails("POST", "/api/jobs/9999/extend", {"cleanerId": a, "minutes": 20}, code="not_found")
    app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": f"{MON}T08:00:00"})
    assert ext(app, j, a, 20)["endMinute"] == 620    # in progress: allowed
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": f"{MON}T10:20:00"})
    app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": a, "minutes": 20}, code="invalid_state")


def test_random_extensions_never_overlap(app):
    rnd = random.Random(1116)
    ids = app.cleaners(6)
    cl = app.client()
    jobs = []
    for _ in range(40):
        req = (date(2026, 11, 16) + timedelta(days=rnd.randrange(5))).isoformat()
        jobs.append(app.book(cl, rnd.choice((1, 1, 2)), max(30, min(480, int(rnd.gauss(248, 105)))), req))
    for _ in range(40):
        j = app.ok("GET", f"/api/jobs/{rnd.choice(jobs)['id']}")
        ext(app, j, rnd.choice(j["cleanerIds"]), 20 * rnd.randint(1, 4))
        assert_no_overlaps(app.ok("GET", "/api/jobs"))
    assert len(app.ok("GET", "/api/jobs")) == 40
