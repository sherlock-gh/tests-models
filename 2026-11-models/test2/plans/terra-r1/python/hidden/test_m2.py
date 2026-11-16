"""Milestone 2 (Terra's plan): the cleaner's day, arrival and departure, extensions and the rebooking they cause (US2)."""
import random
from datetime import date, timedelta

from conftest import MON, TUE, assert_no_overlaps

T = lambda day, hm: f"{day}T{hm}:00"  # noqa: E731


def test_cleaner_day_view(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)                 # a 8-12
    j2 = app.book(cl, 1, 240, MON)                 # b 8-12
    j3 = app.book(cl, 1, 120, MON)                 # a 13-15
    app.book(cl, 1, 60, TUE)
    assert [j["id"] for j in app.ok("GET", f"/api/cleaners/{a}/jobs?date={MON}")] == [j1["id"], j3["id"]]
    assert [j["id"] for j in app.ok("GET", f"/api/cleaners/{b}/jobs?date={MON}")] == [j2["id"]]
    app.fails("GET", f"/api/cleaners/9999/jobs?date={MON}", code="not_found")


def test_arrive_and_depart_use_the_clock(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 2, 240, MON)
    x = app.arrive(j["id"], a, T(MON, "08:02"))
    assert x["status"] == "in_progress"
    w = {r["cleanerId"]: r for r in x["work"]}
    assert w[a]["arrivedAt"] == T(MON, "08:02") and w[b]["arrivedAt"] is None
    x = app.depart(j["id"], a, T(MON, "10:02"))
    w = {r["cleanerId"]: r for r in x["work"]}
    assert (w[a]["departedAt"], w[a]["elapsedSeconds"], x["status"]) == (T(MON, "10:02"), 7200, "in_progress")


def test_bad_sequences_change_nothing(app):
    a, b = sorted(app.cleaners(2))
    c = app.cleaners(1)[0]
    j = app.book(app.client(), 2, 240, MON)
    before = app.state()
    app.fails("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a}, at=T(MON, "09:00"))          # not arrived
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c}, at=T(MON, "08:00"))          # not assigned
    app.fails("POST", "/api/jobs/9999/arrive", {"cleanerId": a}, code="not_found", at=T(MON, "08:00"))
    assert app.state() == before
    app.arrive(j["id"], a, T(MON, "08:00"))
    before = app.state()
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a}, at=T(MON, "08:05"))          # twice
    app.fails("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a}, at=T(MON, "07:59"))          # before arriving
    assert app.state() == before


def started(app, job, cleaners, at=T(MON, "08:00")):
    for c in cleaners:
        app.arrive(job["id"], c, at)


def ext(app, job, cleaner, increments):
    return app.ok("POST", f"/api/jobs/{job['id']}/extend", {"cleanerId": cleaner, "increments": increments})


def test_extension_moves_the_next_job(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)                 # 8:00-12:00
    j2 = app.book(cl, 1, 240, MON)                 # 13:00-17:00
    started(app, j1, [a])
    assert ext(app, j1, a, 1)["endMinute"] == 740
    k = app.ok("GET", f"/api/jobs/{j2['id']}")     # 13:20 + 4 h passes 17:00: Tuesday
    assert (k["date"], k["startMinute"], k["endMinute"], k["cleanerIds"]) == (TUE, 480, 720, [a])


def test_moved_job_starts_an_hour_after_the_new_end(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    first = app.book(cl, 1, 240, MON)              # a 8:00-12:00
    other = app.book(cl, 1, 240, MON)              # b 8:00-12:00
    j2 = app.book(cl, 1, 120, MON)                 # a 13:00-15:00
    assert first["cleanerIds"] == [a] and j2["cleanerIds"] == [a] and j2["startMinute"] == 780
    started(app, first, [a])
    ext(app, first, a, 2)                          # a now ends 12:40
    k = app.ok("GET", f"/api/jobs/{j2['id']}")
    assert (k["date"], k["startMinute"]) == (MON, 820)
    assert app.ok("GET", f"/api/jobs/{other['id']}")["startMinute"] == 480


def test_a_full_hour_left_moves_nothing(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    x = app.book(cl, 1, 240, MON)                  # a 8:00-12:00
    app.book(cl, 1, 260, MON)                      # b 8:00-12:20
    z = app.book(cl, 2, 120, MON)                  # a and b 13:20-15:20
    assert (x["cleanerIds"], z["startMinute"], z["cleanerIds"]) == ([a], 800, [a, b])
    started(app, x, [a])
    ext(app, x, a, 1)                              # a ends 12:20: exactly an hour before 13:20
    assert app.ok("GET", f"/api/jobs/{z['id']}")["startMinute"] == 800
    ext(app, x, a, 1)                              # a ends 12:40: z must start 13:40 or later
    k = app.ok("GET", f"/api/jobs/{z['id']}")
    assert (k["date"], k["startMinute"], k["cleanerIds"]) == (MON, 820, [a, b])


def test_increments_and_late_ends(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 540, MON)        # 8:00-17:00
    app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": a, "increments": 1}, code=("invalid_state", "invalid_input"))   # not started
    started(app, j, [a])
    before = app.state()
    for n in (0, -1, "two", 1.5):
        app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": a, "increments": n}, code="invalid_input")
    assert app.state() == before
    assert ext(app, j, a, 2)["endMinute"] == 1060  # past 17:00 is allowed
    assert ext(app, j, a, 3)["endMinute"] == 1120


def test_extension_refusals(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 1, 120, MON)
    started(app, j, [a])
    app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": b, "increments": 1})            # b is not on it
    app.fails("POST", "/api/jobs/9999/extend", {"cleanerId": a, "increments": 1}, code="not_found")
    assert ext(app, j, a, 1)["endMinute"] == 620


def test_random_extensions_never_overlap(app):
    rnd = random.Random(1116)
    app.cleaners(6)
    cl = app.client()
    jobs = []
    for _ in range(40):
        req = (date(2026, 11, 16) + timedelta(days=rnd.randrange(5))).isoformat()
        jobs.append(app.book(cl, rnd.choice((1, 1, 2)), max(30, min(480, int(rnd.gauss(248, 105)))), req))
    for _ in range(40):
        j = app.ok("GET", f"/api/jobs/{rnd.choice(jobs)['id']}")
        if j["status"] == "scheduled":
            started(app, j, j["cleanerIds"], f"{j['date']}T08:00:00")
        st, out = app.call("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": rnd.choice(j["cleanerIds"]), "increments": rnd.randint(1, 4)})
        # an extension that would crowd a job already under way cannot be satisfied: refused, nothing changed
        assert 200 <= st < 300 or (st == 409 and out["error"]["code"] in ("unschedulable", "invalid_state")), (st, out)
        assert_no_overlaps(app.ok("GET", "/api/jobs"))
    assert len(app.ok("GET", "/api/jobs")) == 40
