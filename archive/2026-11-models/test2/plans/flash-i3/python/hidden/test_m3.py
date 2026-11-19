"""Milestone 3 (Flash-Next's iteration 3 plan): more time (US3) and records with safe deletions (US4)."""
from datetime import datetime, timedelta

from conftest import MON, TUE, WED, T, assert_no_overlaps, spans, start


def more(app, job, cleaner):
    return app.post(f"/api/jobs/{job}/more-time", {"cleaner_id": cleaner})


def test_more_time_needs_an_open_arrive(app):
    # G13: before Arrive, after Depart
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 60, MON)
    app.fails("POST", f"/api/jobs/{j['id']}/more-time", {"cleaner_id": a}, status=(400,))
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    app.tap("depart", j["id"], a, T(MON, "09:00"))
    app.fails("POST", f"/api/jobs/{j['id']}/more-time", {"cleaner_id": a}, status=(400,))
    app.fails("POST", "/api/jobs/9999/more-time", {"cleaner_id": a}, status=(404,))


def test_twenty_minutes_a_step_past_five(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 240, MON)
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    x = more(app, j["id"], a)
    assert spans(x) == [(T(MON, "08:00"), T(MON, "12:20"))] and x["rebooked"] == []
    app.tap("depart", j["id"], a, T(MON, "12:20"))
    late = app.book(app.client("B"), 1, 240, TUE)              # Tue 8:00-12:00
    app.tap("arrive", late["id"], a, T(TUE, "08:00"))
    for _ in range(3):
        x = more(app, late["id"], a)
    assert spans(x) == [(T(TUE, "08:00"), T(TUE, "13:00"))]
    for _ in range(12):
        x = more(app, late["id"], a)
    assert spans(x) == [(T(TUE, "08:00"), T(TUE, "17:00"))]
    x = more(app, late["id"], a)
    assert spans(x) == [(T(TUE, "08:00"), T(TUE, "17:20"))]


def test_a_job_in_the_shadow_is_booked_again(app):
    # G14: an hour after 12:20 is 13:20, so the 13:00 job moves to the first quarter hour after
    (a,) = app.cleaners(1)
    cl = app.client()
    j = app.book(cl, 1, 240, MON)                              # 8:00-12:00
    later = app.book(cl, 1, 60, MON)                           # 13:00-14:00
    assert start(later) == T(MON, "13:00")
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    x = more(app, j["id"], a)
    assert spans(x) == [(T(MON, "08:00"), T(MON, "12:20"))]
    assert [r["job_id"] for r in x["rebooked"]] == [later["id"]]
    moved = app.job(later["id"])
    assert moved["status"] == "booked" and spans(moved) == [(T(MON, "13:30"), T(MON, "14:30"))]
    assert x["rebooked"][0]["parts"] == moved["parts"]
    assert_no_overlaps(app.jobs())


def test_a_bump_leaves_no_overlap(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j = app.book(cl, 1, 240, MON)                              # 8:00-12:00
    b = app.book(cl, 1, 60, MON)                               # 13:00-14:00
    c = app.book(cl, 1, 60, MON)                               # 15:00-16:00
    app.tap("arrive", j["id"], a, T(MON, "08:00"))
    x = more(app, j["id"], a)
    jobs = {k["id"]: k for k in app.jobs()}
    assert b["id"] in [r["job_id"] for r in x["rebooked"]]
    assert all(jobs[i]["status"] == "booked" for i in (b["id"], c["id"]))
    floor = datetime.fromisoformat(T(MON, "13:20"))
    assert all(datetime.fromisoformat(start(jobs[r["job_id"]])) >= floor for r in x["rebooked"])
    assert_no_overlaps(list(jobs.values()))


def test_deleting_a_cleaner_books_their_future_jobs_again(app):
    # G15: two future jobs go to a free cleaner; the job already arrived on is not moved
    (a,) = app.cleaners(1)
    cl = app.client()
    arrived, f1, f2 = app.book(cl, 1, 240, MON), app.book(cl, 1, 240, TUE), app.book(cl, 1, 120, WED)
    assert {*arrived["cleaner_ids"], *f1["cleaner_ids"], *f2["cleaner_ids"]} == {a}
    (b,) = app.cleaners(1, first=1)
    app.tap("arrive", arrived["id"], a, T(MON, "08:00"))
    app.delete(f"/api/cleaners/{a}")
    assert [c["id"] for c in app.get("/api/cleaners")["cleaners"]] == [b]
    for f in (f1, f2):
        g = app.job(f["id"])
        assert g["status"] == "booked" and g["cleaner_ids"] == [b]
        assert g["parts"][0]["start_day"] >= f["requested_day"]
    still = app.job(arrived["id"])
    assert (still["status"], still["parts"]) == ("in_progress", arrived["parts"])
    assert_no_overlaps(app.jobs())


def test_deleting_a_client_cancels_their_future_jobs(app):
    # G16: cancelled jobs stay on file and free their cleaners
    (a,) = app.cleaners(1)
    keep, gone = app.client("Keep"), app.client("Gone")
    j1 = app.book(gone, 1, 240, MON)                           # 8:00-12:00
    j2 = app.book(gone, 1, 60, TUE)
    k = app.book(keep, 1, 60, MON)                             # 13:00
    app.delete(f"/api/clients/{gone}")
    assert [c["id"] for c in app.get("/api/clients")["clients"]] == [keep]
    assert [app.job(j)["status"] for j in (j1["id"], j2["id"])] == ["cancelled", "cancelled"]
    assert app.job(k["id"])["status"] == "booked"
    assert start(app.book(keep, 1, 60, MON)) == T(MON, "08:00")


def test_a_job_with_an_issued_invoice_stays(app):
    # G17, and deleting a job nobody has arrived on frees its slot
    (a,) = app.cleaners(1)
    cl = app.client()
    done = app.book(cl, 1, 60, MON)
    app.tap("arrive", done["id"], a, T(MON, "08:00"))
    inv = app.tap("depart", done["id"], a, T(MON, "09:00"))["invoice"]
    out = app.fails("DELETE", f"/api/jobs/{done['id']}", status=(400,))
    assert "invoice" in out["error"].lower()
    assert app.job(done["id"])["invoice_id"] == inv["id"] and app.invoices() == [inv]
    j = app.book(cl, 1, 60, TUE)
    app.delete(f"/api/jobs/{j['id']}")
    app.fails("GET", f"/api/jobs/{j['id']}", status=(404,))
    assert start(app.book(cl, 1, 60, TUE)) == T(TUE, "08:00")


def test_changing_a_booked_job_books_it_again(app):
    (a,) = app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)                             # 8:00-12:00
    j2 = app.book(cl, 1, 60, MON)                              # 13:00-14:00
    x = app.put(f"/api/jobs/{j2['id']}", {"expected_length_min": 120})
    assert (x["id"], x["expected_length_min"], spans(x)) == (j2["id"], 120, [(T(MON, "13:00"), T(MON, "15:00"))])
    x = app.put(f"/api/jobs/{j1['id']}", {"requested_day": TUE})
    assert (x["requested_day"], spans(x)) == (TUE, [(T(TUE, "08:00"), T(TUE, "12:00"))])
    app.tap("arrive", j2["id"], a, T(MON, "13:00"))
    app.fails("PUT", f"/api/jobs/{j2['id']}", {"expected_length_min": 60}, status=(400,))
    app.fails("PUT", "/api/jobs/9999", {"expected_length_min": 60}, status=(404,))
    assert_no_overlaps(app.jobs())


def test_deleting_records_with_nothing_to_move(app):
    a, b = app.cleaners(2)
    cl, other = app.client(), app.client("Other")
    j = app.book(cl, 1, 60, MON)
    idle = b if a in j["cleaner_ids"] else a
    app.delete(f"/api/cleaners/{idle}")
    app.delete(f"/api/clients/{other}")
    assert app.job(j["id"])["parts"] == j["parts"] and app.job(j["id"])["status"] == "booked"
