"""Milestone 4 (Flash-Next's plan): utilization (US5): worked time on the day of departure, against
8 h a day and 40 h a Monday-to-Sunday week (research D-8)."""
from conftest import MON, NEXT_MON, TUE

WEEK = ["2027-11-15", "2027-11-16", "2027-11-17", "2027-11-18", "2027-11-19"]


def test_day_and_week(app):
    a, b = app.cleaners(2)
    cl = app.client()
    for day in WEEK:                               # a works 6 h each weekday: 30 h in the week
        j = app.book(cl, 1, 6, day)
        app.tap("arrive", a, j["id"], f"{day}T08:00")
        app.tap("depart", a, j["id"], f"{day}T14:00")
    j = app.book(cl, 1, 1, NEXT_MON)               # next week: not counted
    app.tap("arrive", a, j["id"], f"{NEXT_MON}T08:00")
    app.tap("depart", a, j["id"], f"{NEXT_MON}T09:00")
    rows = {u["cleaner_id"]: u for u in app.get(f"/utilization?day={TUE}")}
    assert set(rows) == {a, b}
    assert (rows[a]["day_worked_min"], rows[a]["week_worked_min"]) == (360, 1800)
    assert (rows[b]["day_worked_min"], rows[b]["week_worked_min"]) == (0, 0)


def test_work_counts_on_the_day_of_departure(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 1, MON)
    app.tap("arrive", a, j["id"], f"{MON}T23:00")
    app.tap("depart", a, j["id"], f"{TUE}T01:00")
    (mon,) = app.get(f"/utilization?day={MON}")
    (tue,) = app.get(f"/utilization?day={TUE}")
    assert (mon["day_worked_min"], tue["day_worked_min"], tue["week_worked_min"]) == (0, 120, 120)
