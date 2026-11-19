"""Milestone 2 (Flash-Next's iteration 3 plan): the cleaner's day, Arrive and Depart, invoices
(US2) and settlement (US5)."""
from conftest import MON, TUE, T


def test_the_cleaners_day(app):
    a, b = app.cleaners(2)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)              # a 8-12
    j2 = app.book(cl, 1, 240, MON)              # b 8-12
    j3 = app.book(cl, 1, 120, MON)              # 13-15
    app.book(cl, 1, 60, TUE)
    mine = {c: [j["id"] for j in app.get(f"/api/jobs/today?date={MON}&cleaner_id={c}")["jobs"]] for c in (a, b)}
    assert sorted(mine[a] + mine[b]) == sorted([j1["id"], j2["id"], j3["id"]])
    for c in (a, b):
        starts = [app.job(i)["parts"][0]["start"] for i in mine[c]]
        assert starts == sorted(starts)
    app.fails("GET", f"/api/jobs/today?date={MON}&cleaner_id=9999", status=(404,))


def test_a_split_job_is_on_each_of_its_days(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 600, MON)
    for day in (MON, TUE):
        assert [x["id"] for x in app.get(f"/api/jobs/today?date={day}&cleaner_id={a}")["jobs"]] == [j["id"]]


def test_arrive_and_depart(app):
    a, b = app.cleaners(2)
    j = app.book(app.client(), 2, 240, MON)
    x = app.tap("arrive", j["id"], a, T(MON, "08:02"))
    assert x["status"] == "in_progress"
    assert [(t["cleaner_id"], t["kind"], t["instant"]) for t in x["taps"]] == [(a, "arrive", T(MON, "08:02"))]
    x = app.tap("depart", j["id"], a, T(MON, "10:02"))
    assert x["status"] == "in_progress" and x["invoice_id"] is None and app.invoices() == []
    assert x.get("invoice") is None
    assert [(t["cleaner_id"], t["kind"], t["instant"]) for t in x["taps"]][-1] == (a, "depart", T(MON, "10:02"))


def test_taps_out_of_order_change_nothing(app):
    # G11, G12, and taps that aren't the cleaner's
    a, b, c = app.cleaners(3)
    j = app.book(app.client(), 2, 240, MON)
    on, off = j["cleaner_ids"], [x for x in (a, b, c) if x not in j["cleaner_ids"]][0]
    app.fails("POST", f"/api/jobs/{j['id']}/depart", {"cleaner_id": on[0], "at": T(MON, "09:00")}, status=(400,))
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleaner_id": off, "at": T(MON, "08:00")}, status=(400,))
    app.fails("POST", f"/api/jobs/9999/arrive", {"cleaner_id": on[0], "at": T(MON, "08:00")}, status=(404,))
    app.tap("arrive", j["id"], on[0], T(MON, "08:00"))
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleaner_id": on[0], "at": T(MON, "08:05")}, status=(400,))
    assert len(app.job(j["id"])["taps"]) == 1


def test_a_line_is_billed_to_the_minute(app):
    # G7: Arrive 9:00, Depart 12:30 -> 15750 cents
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 240, MON)
    app.tap("arrive", j["id"], a, T(MON, "09:00"))
    x = app.tap("depart", j["id"], a, T(MON, "12:30"))
    inv = x["invoice"]
    assert (x["status"], x["invoice_id"]) == ("complete", inv["id"])
    assert [(l["cleaner_id"], l["minutes_worked"], l["cents"], l["amount_str"]) for l in inv["lines"]] == [(a, 210, 15750, "$157.50")]
    assert (inv["total_cents"], inv["total_str"], inv["issued_at"], inv["job_id"], inv["settled"]) == \
        (15750, "$157.50", T(MON, "12:30"), j["id"], False)


def test_the_invoice_issues_on_the_last_departure(app):
    # G8: 210 min and 240 min on one invoice -> 15750 + 18000 = 33750 cents
    a, b = app.cleaners(2)
    j = app.book(app.client(), 2, 240, MON)
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    app.tap("arrive", j["id"], b, T(MON, "08:00"))
    assert app.tap("depart", j["id"], b, T(MON, "11:30")).get("invoice") is None
    assert app.invoices() == []
    x = app.tap("depart", j["id"], a, T(MON, "12:00"))
    (inv,) = app.invoices()
    assert x["invoice"] == inv and x["invoice_id"] == inv["id"] and x["status"] == "complete"
    lines = sorted((l["cleaner_id"], l["minutes_worked"], l["cents"]) for l in inv["lines"])
    assert lines == sorted([(a, 240, 18000), (b, 210, 15750)])
    assert (inv["total_cents"], inv["total_str"], inv["issued_at"]) == (33750, "$337.50", T(MON, "12:00"))
    assert app.get(f"/api/invoices/{inv['id']}") == inv
    app.fails("POST", f"/api/jobs/{j['id']}/arrive", {"cleaner_id": a, "at": T(MON, "13:00")}, status=(400,))


def test_a_split_job_is_billed_when_its_last_part_ends(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 600, MON)
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    x = app.tap("depart", j["id"], a, T(MON, "16:00"))
    assert x["status"] == "in_progress" and app.invoices() == []
    app.tap("arrive", j["id"], a, T(TUE, "08:00"))
    x = app.tap("depart", j["id"], a, T(TUE, "10:00"))
    inv = x["invoice"]
    assert [(l["minutes_worked"], l["cents"]) for l in inv["lines"]] == [(600, 45000)]
    assert (inv["total_str"], inv["issued_at"], x["status"]) == ("$450.00", T(TUE, "10:00"), "complete")


def test_settlement(app):
    # G18, G19, G20
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 240, MON)
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    inv = app.tap("depart", j["id"], a, T(MON, "11:23"))["invoice"]      # 203 min: 15225 cents
    assert (inv["total_cents"], inv["total_str"]) == (15225, "$152.25")
    for amount in (15224, 15226, 10000):
        app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amount_cents": amount}, status=(400,))
    app.fails("POST", "/api/invoices/9999/pay", {"amount_cents": 100}, status=(404,))
    assert app.invoices()[0]["settled"] is False
    paid = app.post(f"/api/invoices/{inv['id']}/pay", {"amount_cents": 15225})
    assert paid["settled"] is True and paid["total_cents"] == 15225
    app.fails("POST", f"/api/invoices/{inv['id']}/pay", {"amount_cents": 15225}, status=(400,))
    app.fails("PUT", f"/api/invoices/{inv['id']}", {"total_cents": 1}, status=(400,))
    app.fails("DELETE", f"/api/invoices/{inv['id']}", status=(400,))
    assert [i["settled"] for i in app.invoices()] == [True]


def test_settled_and_unsettled_invoices(app):
    a, b = app.cleaners(2)
    cl = app.client()
    j1, j2 = app.book(cl, 1, 60, MON), app.book(cl, 1, 60, MON)
    invs = []
    for j in (j1, j2):
        c = j["cleaner_ids"][0]
        app.tap("arrive", j["id"], c, T(MON, "08:00"))
        invs.append(app.tap("depart", j["id"], c, T(MON, "09:00"))["invoice"])
    app.post(f"/api/invoices/{invs[1]['id']}/pay", {"amount_cents": 4500})
    assert {i["id"]: i["settled"] for i in app.invoices()} == {invs[0]["id"]: False, invs[1]["id"]: True}


def test_invoices_survive_a_restart(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 60, MON)
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    app.tap("depart", j["id"], a, T(MON, "09:00"))
    invs = app.invoices()
    app.restart()
    assert app.invoices() == invs and app.job(j["id"])["status"] == "complete"
