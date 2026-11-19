"""Milestone 3 (Terra's plan): invoices on the last departure, rounded once, and payment in full (US3)."""
from conftest import MON, TUE

T = lambda day, hm: f"{day}T{hm}:00"  # noqa: E731


def worked(app, job, times):
    """times: {cleaner: (arrive, depart)} on Monday"""
    for c, (a, _) in times.items():
        app.arrive(job["id"], c, T(MON, a))
    for c, (_, d) in times.items():
        app.depart(job["id"], c, T(MON, d))


def test_invoice_on_last_departure(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client("Home 7"), 2, 240, MON)
    app.arrive(j["id"], a, T(MON, "08:00"))
    app.arrive(j["id"], b, T(MON, "08:00"))
    app.depart(j["id"], a, T(MON, "12:00"))
    assert app.ok("GET", "/api/invoices") == []                       # one still working
    x = app.depart(j["id"], b, T(MON, "12:10"))
    assert x["status"] == "completed"
    (inv,) = app.ok("GET", "/api/invoices")
    assert (inv["jobId"], inv["clientName"], inv["issuedAt"], inv["settled"]) == (j["id"], "Home 7", T(MON, "12:10"), False)
    lines = sorted(inv["lines"], key=lambda l: l["cleanerId"])
    assert [(l["cleanerId"], l["elapsedSeconds"]) for l in lines] == [(a, 14400), (b, 15000)]
    assert {l["cleanerName"] for l in lines} == {"Cleaner 0", "Cleaner 1"}
    assert inv["totalCents"] == 36750
    assert app.ok("GET", f"/api/invoices/{inv['id']}") == inv


def test_total_rounded_once(app):
    # 1 s and 1 s: per-line rounding would give 1 + 1 = 2 cents; once, 2 s at 1.25 c/s is 2.5, half up 3
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 2, 60, MON)
    app.arrive(j["id"], a, T(MON, "08:00"))
    app.arrive(j["id"], b, T(MON, "08:00"))
    app.depart(j["id"], a, f"{MON}T08:00:01")
    app.depart(j["id"], b, f"{MON}T08:00:01")
    assert app.ok("GET", "/api/invoices")[0]["totalCents"] == 3


def test_rounding_values(app):
    for secs, cents in ((0, 0), (1, 1), (3, 4), (4, 5), (4980, 6225)):
        c = app.cleaners(1)[0]
        j = app.book(app.client(), 1, 60, MON)
        assert j["cleanerIds"] == [c]
        app.arrive(j["id"], c, T(MON, "08:00"))
        h, r = divmod(secs, 3600)
        app.depart(j["id"], c, f"{MON}T{8 + h:02d}:{r // 60:02d}:{r % 60:02d}")
        assert app.ok("GET", "/api/invoices")[-1]["totalCents"] == cents, secs


def test_pay_in_full_only(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 2, 240, MON)
    worked(app, j, {a: ("08:00", "12:00"), b: ("08:00", "12:10")})
    (inv,) = app.ok("GET", "/api/invoices")
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 30000}, code="payment_mismatch", status=409)
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36751}, code="payment_mismatch")
    assert app.ok("GET", "/api/invoices?settled=false") == [inv]
    assert app.ok("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36750})["settled"] is True
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36750}, code=("invalid_state", "payment_mismatch"), status=409)
    assert app.ok("GET", "/api/invoices?settled=false") == []
    assert [i["id"] for i in app.ok("GET", "/api/invoices?settled=true")] == [inv["id"]]
    app.fails("POST", "/api/invoices/9999/pay", {"amountCents": 1}, code="not_found")


def test_completed_jobs_take_no_taps_and_invoices_last(app):
    a, b = sorted(app.cleaners(2))
    j = app.book(app.client(), 2, 240, MON)
    worked(app, j, {a: ("08:00", "09:00"), b: ("08:00", "09:00")})
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a}, at=T(MON, "10:00"))
    app.fails("POST", f"/api/jobs/{j['id']}/extend", {"cleanerId": a, "increments": 1}, code=("invalid_state", "invalid_input"))
    invs = app.ok("GET", "/api/invoices")
    app.ok("PUT", f"/api/cleaners/{a}", {"name": "Renamed"})
    assert app.ok("GET", "/api/invoices") == invs
    app.restart()
    assert app.ok("GET", "/api/invoices") == invs
