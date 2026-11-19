"""Milestone 4 (Flash-Next's iteration 3 plan): utilization (US6) and the finished app."""
from conftest import FRI, MON, NEXT_MON, THU, TUE, WED, T


def daily(app, day):
    return {e["cleaner_id"]: (e["hours_worked"], e["hours_of"]) for e in app.get(f"/api/utilization/daily?date={day}")["entries"]}


def weekly(app, monday):
    return {e["cleaner_id"]: (e["hours_worked"], e["hours_of"]) for e in app.get(f"/api/utilization/weekly?week_start={monday}")["entries"]}


def work(app, job, cleaner, arrive, depart):
    app.tap("arrive", job, cleaner, arrive)
    app.tap("depart", job, cleaner, depart)


def test_hours_out_of_eight_and_forty(app):
    # US6: 3 h 30 min on Monday is 3.5 of 8; a cleaner with no taps shows 0, not an error
    a, b = app.cleaners(2)
    j = app.book(app.client(), 1, 240, MON)
    c = j["cleaner_ids"][0]
    idle = b if c == a else a
    work(app, j["id"], c, T(MON, "08:00"), T(MON, "11:30"))
    assert daily(app, MON) == {c: (3.5, 8), idle: (0, 8)}
    assert daily(app, TUE) == {c: (0, 8), idle: (0, 8)}
    assert weekly(app, MON) == {c: (3.5, 40), idle: (0, 40)}
    names = {e["cleaner_id"]: e["cleaner_name"] for e in app.get(f"/api/utilization/daily?date={MON}")["entries"]}
    assert names == {a: "Cleaner 0", b: "Cleaner 1"}


def test_work_past_midnight_counts_on_each_day(app):
    # G9: 22:00 to 2:00 is 2 h on each day
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 240, MON)
    work(app, j["id"], a, T(MON, "22:00"), T(TUE, "02:00"))
    assert daily(app, MON) == {a: (2, 8)} and daily(app, TUE) == {a: (2, 8)}
    assert weekly(app, MON) == {a: (4, 40)}


def test_hours_are_not_capped(app):
    # G10: 45 h in a Monday-to-Sunday week shows as 45 of 40; work the next Monday is not in it
    (a,) = app.cleaners(1)
    cl = app.client()
    for day in (MON, TUE, WED, THU, FRI):
        j = app.book(cl, 1, 480, day)
        assert j["parts"][0]["start_day"] == day
        work(app, j["id"], a, T(day, "08:00"), T(day, "17:00"))
    nxt = app.book(cl, 1, 60, NEXT_MON)
    work(app, nxt["id"], a, T(NEXT_MON, "08:00"), T(NEXT_MON, "09:00"))
    assert daily(app, MON) == {a: (9, 8)}
    assert weekly(app, MON) == {a: (45, 40)}
    assert weekly(app, NEXT_MON) == {a: (1, 40)}


def test_bad_report_requests_change_nothing(app):
    app.cleaners(1)
    app.fails("GET", "/api/utilization/daily?date=2027-02-30", status=(400,))
    app.fails("GET", "/api/utilization/weekly?week_start=nope", status=(400,))
