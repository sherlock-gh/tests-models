# Contract: Desktop Back-Office HTTP API (Python app)

Served by `desktop/app.py` on **http://127.0.0.1:$PORT** (loopback only). One
single-page UI at `GET /` (from `desktop/static/index.html`). All API paths below are
under `/api`. Request and response bodies are JSON (UTF-8). Times are local wall-clock
strings (`YYYY-MM-DDTHH:MM`); money is integer cents. Record shapes are exactly
data-model.md.

**Error envelope (FR-019)**: every handled failure returns HTTP 400 (bad input), 404
(unknown id) or 409 (rule violation: overlap, refusal, undeletable, wrong payment) with
body `{"error": "<human-readable message>"}` and **zero changes** to the data file.
Errors are rendered in the page, never as a stack trace or crash.

## Cleaners (FR-001)

| Method+path | Request | Success |
|---|---|---|
| POST /api/cleaners | `{name, phone, email}` | 201 `{cleaner}` (id issued) |
| GET /api/cleaners | — | 200 `{"cleaners": [...]}` |
| GET /api/cleaners/{id} | — | 200 `{cleaner}` / 404 |
| PUT /api/cleaners/{id} | full `{name, phone, email}` | 200 `{cleaner}` / 404 |
| DELETE /api/cleaners/{id} | — | 200 `{"ok": true, "rebooked_job_ids": [...]}` — future jobs re-booked per booking rule, cleaner removed (FR-012) / 404 |

## Clients (FR-001)

Same shape as cleaners with `{name, address, phone}`; DELETE returns
`{"ok": true, "cancelled_job_ids": [...]}` (future jobs cancelled, arrived-at jobs
untouched, FR-012).

## Jobs

| Method+path | Request | Success |
|---|---|---|
| POST /api/jobs | `{client_id, cleaners_needed: 1..3, expected_length_hours: >0, requested_day: "YYYY-MM-DD"}` | 201 `{job}` fully booked by the booking rule (cleaners + parts chosen by the system, FR-002/FR-003); 409 `"No slot in 90 days..."` (FR-006) |
| GET /api/jobs | optional `?from=&to=&client_id=` | 200 `{"jobs": [...]}` |
| GET /api/jobs/{id} | — | 200 `{job}` (parts + assignments embedded) / 404 |
| PUT /api/jobs/{id} | editable job fields as in POST | 200 `{job}` (edit stands as entered; refused 409 if it would leave any assigned cleaner overlapping or <1h-spaced — Q2); 409 on overlap, 404 unknown |
| DELETE /api/jobs/{id} | — | 200 `{"ok": true}` / 409 `"invoice issued"` (FR-013) / 404 |

POST /api/jobs is the **booking rule** exposed: earliest quarter-hour ≥ requested day,
weekdays 8:00–17:00, ≥ clean 1-hour spacing (12:00 end → 13:00 min, never 12:45; 12:10
end → 13:15), >8 h split into 8-hour parts + remainder, each independently booked on
a later workday with the first part's cleaners if free and other free cleaners otherwise,
90-day horizon.

## Invoices & payments (FR-013–FR-016)

| Method+path | Request | Success |
|---|---|---|
| GET /api/invoices | optional `?settled=true\|false` | 200 `{"invoices": [...]}` — settled/unsettled visible (FR-016) |
| GET /api/invoices/{id} | — | 200 `{invoice}` with lines (cleaner name, minutes, amount_cents) + total_cents / 404 |
| POST /api/invoices/{id}/payment | `{amount_cents}` | 200 `{invoice}` (settled, payment embedded) when amount == total_cents exactly; 409 `{"error": "payment must equal total ..."}` otherwise, invoice unchanged |

No invoice edit/delete routes exist (FR-013). Invoices appear only via completion
triggered by mobile-side taps mirrored in this app's own file, or its own tap endpoints
below (both apps enforce the same rules on their own data — research R5).

## Taps in the desktop file (same rules, own data — FR-018)

The back-office page can exercise the field flow against the desktop store (used by
tests and to complete flows on that machine):

| Method+path | Request | Success |
|---|---|---|
| GET /api/day?cleaner_id=&on=YYYY-MM-DD | — | 200 `{"parts": [... jobs with times, client, co-workers]}` (US2-AC1) |
| POST /api/assignments/tap | `{job_id, cleaner_id, kind: "arrive"\|"depart", at: local}` | 200 updated `{job}`; last depart → job complete **and** invoice issued in the same response (FR-014, SC-003); 409 double arrive / depart-without-arrive / depart<arrive (Q5) |
| POST /api/assignments/extend | `{job_id, cleaner_id, minutes: 20, at: local}` | 200 `{job, rebooked_job_ids: [...]}` — +20 min on that cleaner, cascade re-books later jobs ≥ new_end+1h per booking rule (FR-010/FR-011, Q1); may pass 17:00; 409 (atomically, nothing changed) if cascade unplaceable in horizon (Q9) |

## Utilization (FR-017)

| Method+path | Request | Success |
|---|---|---|
| GET /api/utilization?cleaner_id=&from=&to= | — | 200 `{"days": [{"cleaner_id", "date", "minutes", "of": 480}...], "weeks": [{"cleaner_id", "week_start" (Monday), "minutes", "of": 2400}...]}` — uncapped (9h day → `minutes: 540`) |

## Golden vectors both apps must reproduce (see contracts/mobile-logic.md)

210 min → 15750¢; 240 min → 18000¢; lines sum 33750¢ total; Saturday request booked
Monday 8:00; end 12:10 → next allowed start 13:15.
