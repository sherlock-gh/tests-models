# Contract: Desktop Back-Office HTTP API (Python app)

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md)

The desktop app (`desktop/`) serves one local web page at `/` plus a JSON API under
`/api/`. All requests and responses are `application/json` UTF-8; on any rule failure the
response is `400` with `{"error": "<message>"}` and the data file is byte-identical
afterwards; the server never stops (rules-core I10). Unknown ids on reads → `404` with
`{"error": ...}`. IDs in examples are integers; times are `"YYYY-MM-DDTHH:MM"` local
strings; money fields are integer cents plus a display `"$D.CD"` string where noted.

## Endpoints

### Cleaners & clients (CRUD — FR-001)

| Method & path | Body (request) | Success | Errors |
|---|---|---|---|
| `GET /api/cleaners` | — | `{"cleaners":[Cleaner]}` | — |
| `POST /api/cleaners` | `{"name": str}` | `201 Cleaner` | 400 blank name |
| `GET /api/cleaners/{id}` | — | `Cleaner` | 404 unknown id |
| `PUT /api/cleaners/{id}` | `{"name": str}` | `Cleaner` | 400 blank; 404 unknown |
| `DELETE /api/cleaners/{id}` | — | `{"ok":true}` — future jobs rebooked per I9 | 404 unknown |
| same six for `/api/clients` | `{"name": str}` | client delete **cancels** their future jobs | 400/404 |

`Cleaner` = `{"id", "name"}`. `Client` = `{"id", "name"}`.

### Jobs

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/jobs` | — | `{"jobs":[Job]}` (live jobs; cancelled included with `status`) | — |
| `POST /api/jobs` | `{"client_id", "cleaners_needed": 1..3, "expected_length_min": >0, "requested_day": "YYYY-MM-DD"}` | `201 Job` — system-assigned `cleaner_ids`, `parts` per I4 | 400 bad fields; 404 unknown client; 400 `"No slot ... 90 days ..."` message (I5) with store unchanged |
| `GET /api/jobs/{id}` | — | `Job` | 404 |
| `PUT /api/jobs/{id}` | `{expected_length_min?, requested_day?}` on a **booked, not-yet-deleted** job ⇒ it is cancelled and rebooked by the booking rule | `Job` | 400 if invoice issued / arrived-on; 404 |
| `DELETE /api/jobs/{id}` | — | `{"ok":true}` (job removed; if booked it leaves the schedule cleanly) | 400 `"job's invoice has been issued"` (I9); 404 |

`Job` = `{"id","client_id","client_name","cleaners_needed","expected_length_min",
"requested_day","cleaner_ids","status","parts":[{"start_day","start","end","duration_min"}],
"invoice_id"|"invoice"?, "taps":[{"cleaner_id","kind","instant"}]}`.

### Field operations exposed for demo/testing (the real field app is `CleaningKit`)

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/jobs/today?date=YYYY-MM-DD&cleaner_id=N` | — | `{"jobs":[Job]}` assigned to that cleaner starting that day (US2 AC1) | 400/404 |
| `POST /api/jobs/{id}/arrive` | `{"cleaner_id"}` | `Job` (tap recorded to the minute; first arrival ⇒ `in_progress`) | 400 second Arrive / wrong cleaner / future part not started |
| `POST /api/jobs/{id}/depart` | `{"cleaner_id"}` | `Job` + `invoice` **when last cleaner departs** (`Job`, `invoice.issued_at` now) | 400 Depart without Arrive |
| `POST /api/jobs/{id}/more-time` | `{"cleaner_id"}` | `20 min` extension applied, `Job` + any `rebooked:[{job_id, parts}]` (I14/G14) | 400 not-arrived/finished |

### Invoices & settlement (FR-013/FR-014)

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/invoices` | — | `{"invoices":[Invoice]}` each with `"settled": bool` | — |
| `GET /api/invoices/{id}` | — | `Invoice` | 404 |
| `POST /api/invoices/{id}/pay` | `{"amount_cents": int}` | `Invoice` now `settled:true` when `amount_cents == total_cents` | 400 other amount / already settled / 404 |
| `PUT/DELETE /api/invoices*` | any | — | 400 always (issued invoices never change/delete) |

`Invoice` = `{"id","job_id","issued_at","lines":[{"cleaner_id","cleaner_name",
"minutes_worked","cents","amount_str"}],"total_cents","total_str","settled"}` with
goldens G7/G8 (`15750`/`18000`/`33750`).

### Utilization (FR-015)

| Method & path | Query | Success |
|---|---|---|
| `GET /api/utilization/daily?date=YYYY-MM-DD` | — | `{"entries":[{"cleaner_id","cleaner_name","hours_worked","hours_of":8}]}` — midnight-split minutes attributed per G9; no-tap cleaner → `0.0` |
| `GET /api/utilization/weekly?week_start=YYYY-MM-DD` (a Monday) | — | same shape with `hours_of: 40`; values may exceed (G10) |

Bad dates / unknown cleaner → 400/404 with message, nothing stored changes.
