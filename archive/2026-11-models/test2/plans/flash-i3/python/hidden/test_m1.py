"""Milestone 1 (Flash-Next's iteration 3 plan): setup, foundation, records and booking (US1)."""
from datetime import date, timedelta

from conftest import FRI, MON, NEXT_MON, NO_SLOT, SAT, TUE, T, assert_no_overlaps, spans, start


def test_the_page_is_served(app):
    st, out = app.call("GET", "/")
    assert st == 200 and "<html" in str(out).lower()


def test_cleaner_and_client_records(app):
    for kind in ("cleaners", "clients"):
        a = app.post(f"/api/{kind}", {"name": "Ann"})
        st, _ = app.call("POST", f"/api/{kind}", {"name": "Bo"})
        assert st == 201
        assert a["name"] == "Ann" and isinstance(a["id"], int)
        assert app.get(f"/api/{kind}/{a['id']}") == a
        assert app.put(f"/api/{kind}/{a['id']}", {"name": "Anna"})["name"] == "Anna"
        assert [r["name"] for r in app.get(f"/api/{kind}")[kind]] == ["Anna", "Bo"]
        app.fails("POST", f"/api/{kind}", {"name": "   "}, status=(400,))
        app.fails("PUT", f"/api/{kind}/{a['id']}", {"name": ""}, status=(400,))
        app.fails("GET", f"/api/{kind}/9999", status=(404,))
        app.fails("PUT", f"/api/{kind}/9999", {"name": "X"}, status=(404,))
        app.delete(f"/api/{kind}/{a['id']}")
        assert [r["name"] for r in app.get(f"/api/{kind}")[kind]] == ["Bo"]
        app.fails("DELETE", f"/api/{kind}/{a['id']}", status=(404,))


def test_records_are_kept_in_the_data_file(app):
    (a,) = app.cleaners(1)
    j = app.book(app.client(), 1, 60, MON)
    assert app.data.exists()
    app.restart()
    assert [c["id"] for c in app.get("/api/cleaners")["cleaners"]] == [a]
    assert app.job(j["id"]) == j


def test_shadow_after_a_whole_hour(app):
    # G1: a job ending 12:00 leaves 13:00 as the earliest next start, not 12:45
    (a,) = app.cleaners(1)
    cl = app.client()
    j1 = app.book(cl, 1, 240, MON)
    assert (j1["cleaner_ids"], spans(j1), j1["status"]) == ([a], [(T(MON, "08:00"), T(MON, "12:00"))], "booked")
    assert j1["parts"][0]["duration_min"] == 240 and j1["invoice_id"] is None
    j2 = app.book(cl, 1, 60, MON)
    assert spans(j2) == [(T(MON, "13:00"), T(MON, "14:00"))]


def test_shadow_to_the_next_quarter_hour(app):
    # G2: a job ending 12:10 leaves 13:15
    app.cleaners(1)
    cl = app.client()
    assert spans(app.book(cl, 1, 250, MON)) == [(T(MON, "08:00"), T(MON, "12:10"))]
    assert start(app.book(cl, 1, 30, MON)) == T(MON, "13:15")


def test_a_minute_past_the_hour_is_inside_the_shadow(app):
    app.cleaners(1)
    cl = app.client()
    assert spans(app.book(cl, 1, 241, MON)) == [(T(MON, "08:00"), T(MON, "12:01"))]
    assert start(app.book(cl, 1, 30, MON)) == T(MON, "13:15")      # 13:00 is 59 minutes after


def test_saturday_goes_to_monday(app):
    # G3
    app.cleaners(1)
    j = app.book(app.client(), 1, 120, SAT)
    assert spans(j) == [(T(NEXT_MON, "08:00"), T(NEXT_MON, "10:00"))] and j["requested_day"] == SAT


def test_a_job_that_does_not_fit_today_goes_to_the_next_workday(app):
    app.cleaners(1)
    cl = app.client()
    app.book(cl, 1, 420, MON)                                  # 8:00-15:00
    assert start(app.book(cl, 1, 120, MON)) == T(TUE, "08:00")  # 16:00-18:00 would pass 17:00


def test_an_eight_hour_job_is_one_part(app):
    # G4
    app.cleaners(1)
    j = app.book(app.client(), 1, 480, MON)
    assert spans(j) == [(T(MON, "08:00"), T(MON, "16:00"))]


def test_a_ten_hour_job_splits_across_two_workdays(app):
    # G5: 8 h on the first workday, 2 h on the next, the same crew
    app.cleaners(3)
    cl = app.client()
    j = app.book(cl, 2, 600, MON)
    assert spans(j) == [(T(MON, "08:00"), T(MON, "16:00")), (T(TUE, "08:00"), T(TUE, "10:00"))]
    assert [p["duration_min"] for p in j["parts"]] == [480, 120] and len(set(j["cleaner_ids"])) == 2
    f = app.book(cl, 1, 600, FRI)                              # Friday's next workday is Monday
    assert spans(f) == [(T(FRI, "08:00"), T(FRI, "16:00")), (T(NEXT_MON, "08:00"), T(NEXT_MON, "10:00"))]
    assert_no_overlaps(app.jobs())


def test_cleaners_assigned_by_the_system(app):
    cs = app.cleaners(3)
    cl = app.client()
    for n in (1, 2, 3):
        j = app.book(cl, n, 60, MON)
        assert len(j["cleaner_ids"]) == n and set(j["cleaner_ids"]) <= set(cs)
    for _ in range(6):
        app.book(cl, 2, 90, MON)
    assert_no_overlaps(app.jobs())


def test_the_ninety_day_search(app):
    # G6: one cleaner and eight-hour jobs: a weekday each. Monday to Monday + 90 days holds 65.
    app.cleaners(1)
    cl = app.client()
    last = None
    for _ in range(65):
        last = app.book(cl, 1, 480, MON)
    assert last["parts"][0]["start_day"] == (date.fromisoformat(MON) + timedelta(days=88)).isoformat()
    out = app.fails("POST", "/api/jobs", {"client_id": cl, "cleaners_needed": 1, "expected_length_min": 480, "requested_day": MON}, status=(400,))
    assert NO_SLOT in out["error"]
    assert len(app.jobs()) == 65


def test_too_few_cleaners_is_refused(app):
    app.cleaners(2)
    cl = app.client()
    app.fails("POST", "/api/jobs", {"client_id": cl, "cleaners_needed": 3, "expected_length_min": 60, "requested_day": MON}, status=(400,))
    assert app.jobs() == []


def test_bad_booking_requests_change_nothing(app):
    app.cleaners(3)
    cl = app.client()
    app.book(cl, 1, 60, MON)
    good = {"client_id": cl, "cleaners_needed": 1, "expected_length_min": 60, "requested_day": MON}
    for change in ({"cleaners_needed": 0}, {"cleaners_needed": 4}, {"expected_length_min": 0},
                   {"expected_length_min": -30}, {"requested_day": "2027-13-40"}):
        app.fails("POST", "/api/jobs", {**good, **change}, status=(400,))
    app.fails("POST", "/api/jobs", {**good, "client_id": 9999}, status=(404,))
    app.fails("GET", "/api/jobs/9999", status=(404,))
    assert len(app.jobs()) == 1
