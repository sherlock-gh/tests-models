"""Milestone 4: utilization, and the whole app still working (plan US6; C16)."""
from conftest import MON

WEEK = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]


def test_c16_day_and_week(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    for day in WEEK:                               # a works 6 h each weekday: 30 h in the week
        j = app.book(cl, 1, 360, day)
        assert j["cleanerIds"] == [a]
        app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": f"{day}T08:00:00"})
        app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": f"{day}T14:00:00"})
    nxt = app.book(cl, 1, 60, "2026-11-23")        # next week: not counted
    app.ok("POST", f"/api/jobs/{nxt['id']}/arrive", {"cleanerId": a, "timestamp": "2026-11-23T08:00:00"})
    app.ok("POST", f"/api/jobs/{nxt['id']}/depart", {"cleanerId": a, "timestamp": "2026-11-23T09:00:00"})
    rows = {u["cleanerId"]: u for u in app.ok("GET", "/api/utilization?date=2026-11-17")}
    assert set(rows) == {a, b}
    u = rows[a]
    assert (u["date"], u["daySeconds"], u["weekSeconds"]) == ("2026-11-17", 21600, 108000)
    assert abs(u["dayPercent"] - 75) < 0.01 and abs(u["weekPercent"] - 75) < 0.01
    assert (rows[b]["daySeconds"], rows[b]["weekSeconds"], rows[b]["dayPercent"]) == (0, 0, 0)


def test_work_counts_on_the_day_of_arrival(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 60, MON)
    app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": f"{MON}T23:00:00"})
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": "2026-11-17T01:00:00"})
    (mon,) = app.ok("GET", f"/api/utilization?date={MON}")
    (tue,) = app.ok("GET", "/api/utilization?date=2026-11-17")
    assert (mon["daySeconds"], tue["daySeconds"], tue["weekSeconds"]) == (7200, 0, 7200)


def test_utilization_refuses_a_bad_date(app):
    app.cleaners(1)
    app.fails("GET", "/api/utilization?date=17/11/2026", code="invalid_input")
