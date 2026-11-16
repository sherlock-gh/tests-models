"""Milestone 2: the cleaner's day, Arrive and Depart, invoices and payment (plan US3, US4; C8-C12, C17)."""
from conftest import MON, TUE

T = lambda day, hm: f"{day}T{hm}:00"  # noqa: E731


def two_cleaner_job(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client("Home 7")
    j = app.book(cl, 2, 240, MON)
    return a, b, cl, j


def test_cleaner_day_view(app):
    a, b = sorted(app.cleaners(2))
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)                 # a 8-12
    j2 = app.book(cl, 1, 240, MON)                 # b 8-12
    j3 = app.book(cl, 1, 120, MON)                 # a 13-15
    app.book(cl, 1, 60, TUE)
    day = app.ok("GET", f"/api/cleaners/{a}/day?date={MON}")
    assert [j["id"] for j in day] == [j1["id"], j3["id"]]
    assert [j["id"] for j in app.ok("GET", f"/api/cleaners/{b}/day?date={MON}")] == [j2["id"]]
    app.fails("GET", f"/api/cleaners/9999/day?date={MON}", code="not_found")


def test_arrive_and_depart(app):
    a, b, cl, j = two_cleaner_job(app)
    x = app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": T(MON, "08:02")})
    assert x["status"] == "in_progress"
    e = {t["cleanerId"]: t for t in x["timeEntries"]}
    assert e[a]["arrivedAt"] == T(MON, "08:02") and e[b]["arrivedAt"] is None
    x = app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": T(MON, "10:02")})
    e = {t["cleanerId"]: t for t in x["timeEntries"]}
    assert e[a]["secondsWorked"] == 7200 and x["status"] == "in_progress"


def test_c9_bad_sequences_change_nothing(app):
    a, b, cl, j = two_cleaner_job(app)
    c = app.cleaners(1)[0]
    before = app.state()
    app.fails("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": T(MON, "09:00")}, code="invalid_state")
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})   # not assigned
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": "8 o'clock"}, code="invalid_input")
    app.fails("POST", "/api/jobs/9999/arrive", {"cleanerId": a, "timestamp": T(MON, "08:00")}, code="not_found")
    assert app.state() == before
    app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": T(MON, "08:00")})
    before = app.state()
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": T(MON, "08:05")}, code="invalid_state")
    app.fails("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": T(MON, "07:59")})   # before arriving
    assert app.state() == before


def test_c10_c11_invoice_on_last_departure(app):
    a, b, cl, j = two_cleaner_job(app)
    for c in (a, b):
        app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": T(MON, "12:00")})
    assert app.ok("GET", "/api/invoices") == []                       # C11: one still working
    x = app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": b, "timestamp": T(MON, "12:10")})
    assert x["status"] == "complete"
    (inv,) = app.ok("GET", "/api/invoices")
    assert inv["jobId"] == j["id"] and inv["clientName"] == "Home 7" and inv["settled"] is False
    lines = sorted(inv["lines"], key=lambda l: l["cleanerId"])
    assert [(l["cleanerId"], l["secondsWorked"], l["chargeCents"]) for l in lines] == [(a, 14400, 18000), (b, 15000, 18750)]
    assert {l["cleanerName"] for l in lines} == {"Cleaner 0", "Cleaner 1"}
    assert inv["totalCents"] == 36750
    assert app.ok("GET", f"/api/invoices/{inv['id']}") == inv


def worked(app, seconds):
    """A one-cleaner job worked for `seconds`: its invoice"""
    c = app.cleaners(1)[0]
    j = app.book(app.client(), 1, 60, MON)
    app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": c, "timestamp": f"{MON}T{8 + h:02d}:{m:02d}:{s:02d}"})
    return app.ok("GET", "/api/invoices")[-1]


def test_c17_rounding_to_the_nearest_cent(app):
    # $45 an hour is 1.25 cents a second: halves round up
    for secs, cents in ((0, 0), (1, 1), (2, 3), (3, 4), (4, 5), (4980, 6225)):
        inv = worked(app, secs)
        assert inv["lines"][0]["chargeCents"] == cents and inv["totalCents"] == cents, (secs, inv)


def test_c12_pay_in_full_only(app):
    a, b, cl, j = two_cleaner_job(app)
    for c in (a, b):
        app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": a, "timestamp": T(MON, "12:00")})
    app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": b, "timestamp": T(MON, "12:10")})
    (inv,) = app.ok("GET", "/api/invoices")
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 30000}, code="payment_mismatch", status=409)
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36751}, code="payment_mismatch")
    assert app.ok("GET", "/api/invoices?settled=false") == [inv]
    assert app.ok("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36750})["settled"] is True
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amountCents": 36750}, code="invalid_state", status=409)
    assert app.ok("GET", "/api/invoices?settled=false") == []
    assert [i["id"] for i in app.ok("GET", "/api/invoices?settled=true")] == [inv["id"]]
    app.fails("POST", "/api/invoices/9999/pay", {"amountCents": 1}, code="not_found")


def test_c8_invoices_keep_their_names(app):
    a, b, cl, j = two_cleaner_job(app)
    later = app.book(cl, 1, 120, TUE)
    for c in (a, b):
        app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})
        app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": c, "timestamp": T(MON, "11:00")})
    (inv,) = app.ok("GET", "/api/invoices")
    app.ok("PUT", f"/api/cleaners/{a}", {"name": "Renamed"})
    app.ok("DELETE", f"/api/clients/{cl}")
    assert app.ok("GET", "/api/invoices") == [inv]
    assert app.ok("GET", f"/api/jobs/{later['id']}")["status"] == "cancelled"
    assert app.ok("GET", f"/api/jobs/{j['id']}")["status"] == "complete"


def test_completed_and_cancelled_jobs_take_no_taps(app):
    a, b, cl, j = two_cleaner_job(app)
    for c in (a, b):
        app.ok("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": c, "timestamp": T(MON, "08:00")})
        app.ok("POST", f"/api/jobs/{j['id']}/depart", {"cleanerId": c, "timestamp": T(MON, "09:00")})
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleanerId": a, "timestamp": T(MON, "10:00")})
    k = app.book(cl, 1, 60, TUE)
    app.ok("DELETE", f"/api/clients/{cl}")
    app.fails("POST", f"/api/jobs/{k['id']}/arrive", {"cleanerId": k["cleanerIds"][0], "timestamp": T(TUE, "08:00")})
    assert len(app.ok("GET", "/api/invoices")) == 1


def test_invoices_survive_a_restart(app):
    inv = worked(app, 3600)
    app.restart()
    assert app.ok("GET", "/api/invoices") == [inv]
