"""Milestone 4 (Terra's plan): removals and utilization (US4)."""
from conftest import BEFORE, MON, TUE

T = lambda day, hm: f"{day}T{hm}:00"  # noqa: E731


def test_client_removal_cancels_future_jobs_only(app):
    (a,) = app.cleaners(1)
    keep, gone = app.client("Keep"), app.client("Gone")
    done = app.book(gone, 1, 60, MON)               # 8:00-9:00, worked and invoiced
    later = app.book(gone, 1, 120, MON)             # 10:00-12:00
    nxt = app.book(gone, 1, 120, TUE)
    app.arrive(done["id"], a, T(MON, "08:00"))
    app.depart(done["id"], a, T(MON, "09:00"))
    invs = app.ok("GET", "/api/invoices")
    app.ok("DELETE", f"/api/clients/{gone}", at=T(MON, "09:30"))
    assert app.ok("GET", f"/api/jobs/{later['id']}")["status"] == "cancelled"
    assert app.ok("GET", f"/api/jobs/{nxt['id']}")["status"] == "cancelled"
    assert app.ok("GET", f"/api/jobs/{done['id']}")["status"] == "completed"
    assert app.ok("GET", "/api/invoices") == invs
    app.fails("GET", f"/api/clients/{gone}", code="not_found")
    assert app.book(keep, 1, 120, MON)["startMinute"] == 600   # cancelled jobs block no one


def test_jobs_already_started_or_past_are_not_future(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    past = app.book(cl, 1, 60, MON)                 # 8:00, not started, but before "now"
    app.ok("DELETE", f"/api/clients/{cl}", at=T(MON, "09:00"))
    assert app.ok("GET", f"/api/jobs/{past['id']}")["status"] == "scheduled"


def test_cleaner_removal_rebooks_future_jobs(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 1, 240, MON)
    assert j["cleanerIds"] == [a]
    app.ok("DELETE", f"/api/cleaners/{a}", at=BEFORE)
    k = app.ok("GET", f"/api/jobs/{j['id']}")
    assert (k["date"], k["startMinute"], k["cleanerIds"], k["status"]) == (MON, 480, [b], "scheduled")
    app.fails("GET", f"/api/cleaners/{a}", code="not_found")


def test_cleaner_removal_refused_when_a_job_cannot_be_rebooked(app):
    (a,) = app.cleaners(1)
    app.book(app.client(), 1, 240, MON)
    before = app.state()
    app.fails("DELETE", f"/api/cleaners/{a}", code=("unschedulable", "invalid_state"), at=BEFORE)
    assert app.state() == before


def test_day_and_week(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    for day in ("2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"):
        j = app.book(cl, 1, 360, day)
        assert j["cleanerIds"] == [a]
        app.arrive(j["id"], a, T(day, "08:00"))
        app.depart(j["id"], a, T(day, "14:00"))
    nxt = app.book(cl, 1, 60, "2026-11-23")        # next week: not counted
    app.arrive(nxt["id"], a, T("2026-11-23", "08:00"))
    app.depart(nxt["id"], a, T("2026-11-23", "09:00"))
    u = app.ok("GET", f"/api/utilization?cleanerId={a}&date={TUE}")
    assert (u["cleanerId"], u["date"], u["daySeconds"], u["weekSeconds"]) == (a, TUE, 21600, 108000)
    v = app.ok("GET", f"/api/utilization?cleanerId={b}&date={TUE}")
    assert (v["daySeconds"], v["weekSeconds"]) == (0, 0)
    app.fails("GET", f"/api/utilization?cleanerId=9999&date={TUE}", code="not_found")
    app.fails("GET", f"/api/utilization?cleanerId={a}&date=17/11/2026", code="invalid_input")


def test_only_completed_work_counts_split_at_midnight(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    j = app.book(cl, 1, 60, MON)
    app.arrive(j["id"], a, T(MON, "23:00"))
    app.depart(j["id"], a, T(TUE, "01:30"))        # 1 h on Monday, 1.5 h on Tuesday
    k = app.book(cl, 2, 60, TUE)                   # under way: not counted
    app.arrive(k["id"], a, T(TUE, "10:00"))
    app.arrive(k["id"], b, T(TUE, "10:00"))
    app.depart(k["id"], a, T(TUE, "11:00"))
    mon = app.ok("GET", f"/api/utilization?cleanerId={a}&date={MON}")
    tue = app.ok("GET", f"/api/utilization?cleanerId={a}&date={TUE}")
    assert (mon["daySeconds"], tue["daySeconds"], tue["weekSeconds"]) == (3600, 5400, 9000)
