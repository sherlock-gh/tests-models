"""Milestone 3 (Flash-Next's plan): extensions and their rebooking, and removals (US4)."""
from conftest import MON, TUE, cleaners_of, slot

T = lambda hm, day=MON: f"{day}T{hm}"  # noqa: E731


def extend(app, cleaner, job):
    return app.post(f"/field/{cleaner}/jobs/{job['id']}/extend")


def test_extension_moves_the_next_job(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 4, MON)                   # 8:00-12:00
    j2 = app.book(cl, 1, 4, MON)                   # 13:00-17:00
    app.tap("arrive", a, j1["id"], T("08:00"))
    assert extend(app, a, j1)["booked_end"] == T("12:20")
    k = app.get(f"/jobs/{j2['id']}")              # 13:20 + 4 h passes 17:00: Tuesday
    assert (slot(k), cleaners_of(k), k["state"]) == ((TUE, 480), [a], "scheduled")


def test_moved_job_starts_an_hour_after_the_new_end(app):
    a, b = app.cleaners(2)
    cl = app.client()
    first = app.book(cl, 1, 4, MON)                # a 8:00-12:00
    other = app.book(cl, 1, 4, MON)                # b 8:00-12:00
    j2 = app.book(cl, 1, 2, MON)                   # a 13:00-15:00
    assert cleaners_of(first) == [a] and cleaners_of(j2) == [a] and slot(j2) == (MON, 780)
    app.tap("arrive", a, first["id"], T("08:00"))
    extend(app, a, first)
    extend(app, a, first)                          # a now ends 12:40
    assert slot(app.get(f"/jobs/{j2['id']}")) == (MON, 820)
    assert slot(app.get(f"/jobs/{other['id']}")) == (MON, 480)


def test_more_than_an_hour_left_moves_nothing(app):
    a, b = app.cleaners(2)
    cl = app.client()
    x = app.book(cl, 1, 4, MON)                    # a 8:00-12:00
    app.book(cl, 1, 4.5, MON)                      # b 8:00-12:30
    z = app.book(cl, 2, 2, MON)                    # a and b 13:30-15:30
    assert (cleaners_of(x), slot(z), cleaners_of(z)) == ([a], (MON, 810), [a, b])
    app.tap("arrive", a, x["id"], T("08:00"))
    extend(app, a, x)                              # a ends 12:20: 70 minutes before 13:30
    assert slot(app.get(f"/jobs/{z['id']}")) == (MON, 810)
    extend(app, a, x)                              # a ends 12:40: z must start 13:40 or later
    k = app.get(f"/jobs/{z['id']}")
    assert (slot(k), cleaners_of(k)) == ((MON, 820), [a, b])


def test_extensions_may_pass_five(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 9, MON)          # 8:00-17:00
    app.tap("arrive", a, j["id"], T("08:00"))
    extend(app, a, j)
    assert extend(app, a, j)["booked_end"] == T("17:40")


def test_cleaner_removal_rebooks_future_jobs(app):
    a, b = app.cleaners(2)
    j = app.book(app.client(), 1, 4, MON)
    assert cleaners_of(j) == [a]
    app.post(f"/cleaners/{a}/delete")
    k = app.get(f"/jobs/{j['id']}")
    assert (slot(k), cleaners_of(k), k["state"]) == ((MON, 480), [b], "scheduled")
    app.fails("GET", f"/cleaners/{a}", codes=("not_found",))


def test_cleaner_removal_refused_when_a_job_would_be_stranded(app):
    (a,) = app.cleaners(1)
    app.book(app.client(), 1, 4, MON)
    before = app.state()
    app.fails("POST", f"/cleaners/{a}/delete", codes=("not_enough_cleaners",))
    assert app.state() == before


def test_client_removal_cancels_future_jobs_and_keeps_invoices(app):
    (a,) = app.cleaners(1)
    keep, gone = app.client("Keep"), app.client("Gone")
    done = app.book(gone, 1, 1, MON)               # 8:00-9:00, worked and invoiced
    later = app.book(gone, 1, 2, TUE)
    app.tap("arrive", a, done["id"], T("08:00"))
    app.tap("depart", a, done["id"], T("09:00"))
    invs = app.get("/invoices")
    app.post(f"/clients/{gone}/delete")
    assert app.get(f"/jobs/{later['id']}")["state"] == "cancelled"
    assert app.get(f"/jobs/{done['id']}")["state"] == "complete"
    assert app.get("/invoices") == invs
    assert slot(app.book(keep, 1, 2, TUE)) == (TUE, 480)            # a cancelled job blocks no one
