"""Milestone 2 (Flash-Next's plan): the cleaner's day, Arrive and Depart, invoices and settlement (US2, US3)."""
from conftest import MON, TUE, cleaners_of

T = lambda hm, day=MON: f"{day}T{hm}"  # noqa: E731


def test_field_day(app):
    a, b = app.cleaners(2)
    cl = app.client()
    j1 = app.book(cl, 1, 4, MON)                   # a 8-12
    j2 = app.book(cl, 1, 4, MON)                   # b 8-12
    j3 = app.book(cl, 1, 2, MON)                   # a 13-15
    app.book(cl, 1, 1, TUE)
    assert [j["id"] for j in app.get(f"/field/{a}/today?day={MON}")] == [j1["id"], j3["id"]]
    assert [j["id"] for j in app.get(f"/field/{b}/today?day={MON}")] == [j2["id"]]


def test_arrive_and_depart(app):
    a, b = app.cleaners(2)
    j = app.book(app.client(), 2, 4, MON)
    x = app.tap("arrive", a, j["id"], T("08:02"))
    assert x["state"] == "in_progress"
    w = {s["cleaner_id"]: s for s in x["assignments"]}
    assert w[a]["arrival"] == T("08:02") and w[b]["arrival"] is None
    x = app.tap("depart", a, j["id"], T("10:02"))
    w = {s["cleaner_id"]: s for s in x["assignments"]}
    assert (w[a]["departure"], w[a]["worked_min"], x["state"]) == (T("10:02"), 120, "in_progress")


def test_taps_out_of_order_change_nothing(app):
    a, b = app.cleaners(2)
    c = app.cleaners(1)[0]
    j = app.book(app.client(), 2, 4, MON)
    before = app.state()
    app.fails("POST", f"/field/{a}/jobs/{j['id']}/depart", {"at": T("09:00")}, codes=("tap_out_of_order",))
    app.fails("POST", f"/field/{c}/jobs/{j['id']}/arrive", {"at": T("08:00")}, codes=("wrong_cleaner",))
    app.fails("POST", f"/field/{a}/jobs/9999/arrive", {"at": T("08:00")}, codes=("not_found",))
    assert app.state() == before
    app.tap("arrive", a, j["id"], T("08:00"))
    before = app.state()
    app.fails("POST", f"/field/{a}/jobs/{j['id']}/arrive", {"at": T("08:05")}, codes=("tap_out_of_order",))
    app.fails("POST", f"/field/{a}/jobs/{j['id']}/depart", {"at": T("07:59")})          # before the arrival
    assert app.state() == before


def test_invoice_on_the_last_departure(app):
    # The plan's own example (US3-AC1): 4.0 h and 3.5 h -> $180.00 + $157.50 = $337.50
    a, b = app.cleaners(2)
    j = app.book(app.client(), 2, 4, MON)
    app.tap("arrive", a, j["id"], T("08:00"))
    app.tap("arrive", b, j["id"], T("08:00"))
    app.tap("depart", b, j["id"], T("11:30"))
    assert app.get("/invoices") == []                                    # one still working
    x = app.tap("depart", a, j["id"], T("12:00"))
    assert x["state"] == "complete"
    (inv,) = app.get("/invoices")
    assert (inv["job_id"], inv["issued_at"], inv["settled"], x["invoice_id"]) == (j["id"], T("12:00"), False, inv["id"])
    lines = sorted(inv["lines"], key=lambda l: l["cleaner_id"])
    assert [(l["cleaner_id"], l["worked_min"], l["amount"]) for l in lines] == [(a, 240, "180.00"), (b, 210, "157.50")]
    assert inv["total"] == "337.50"
    assert app.get(f"/invoices/{inv['id']}") == inv


def test_equal_taps_make_a_zero_line(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 1, MON)
    app.tap("arrive", a, j["id"], T("08:00"))
    app.tap("depart", a, j["id"], T("08:00"))
    (inv,) = app.get("/invoices")
    assert (inv["lines"][0]["amount"], inv["total"]) == ("0.00", "0.00")


def test_settlement(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 4, MON)
    app.tap("arrive", a, j["id"], T("08:00"))
    app.tap("depart", a, j["id"], T("11:23"))     # 203 min: $152.25
    (inv,) = app.get("/invoices")
    assert inv["total"] == "152.25"
    before = app.state(invoices=True)
    app.fails("POST", f"/invoices/{inv['id']}/pay", {"amount": "100.00"}, codes=("payment_amount_mismatch",))
    app.fails("POST", f"/invoices/{inv['id']}/pay", {"amount": "152.26"}, codes=("payment_amount_mismatch",))
    app.fails("POST", "/invoices/9999/pay", {"amount": "1.00"}, codes=("not_found",))
    assert app.state(invoices=True) == before
    paid = app.post(f"/invoices/{inv['id']}/pay", {"amount": "152.25"})
    assert paid["settled"] is True and paid["payment_amount"] == "152.25" and paid["payment_date"]
    app.fails("POST", f"/invoices/{inv['id']}/pay", {"amount": "152.25"}, codes=("already_settled",))
    assert [i["settled"] for i in app.get("/invoices")] == [True]


def test_invoices_survive_a_restart(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 1, MON)
    app.tap("arrive", a, j["id"], T("08:00"))
    app.tap("depart", a, j["id"], T("09:00"))
    invs = app.get("/invoices")
    app.restart()
    assert app.get("/invoices") == invs and cleaners_of(app.get(f"/jobs/{j['id']}")) == [a]
