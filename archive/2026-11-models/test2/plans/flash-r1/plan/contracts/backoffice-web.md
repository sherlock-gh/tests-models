# Contract: Back-Office Web Pages (webapp/)

**Form**: HTTP routes + HTML forms on 127.0.0.1 (port 18080–18089 for validation). Pages follow the back-office view of `shared/rule-spec.md`; data lives in one local JSON file (`webapp/data/store.json`). No auth (out of scope).

## Pages & actions

| Method | Path | Purpose | Result |
|---|---|---|---|
| GET | `/` | Back-office dashboard: links to all lists | 200 page |
| GET/POST | `/cleaners` | List / create cleaner (name) | 200; POST→redirect on success; error banner + no change on bad input (FR-001, FR-016) |
| GET/POST | `/cleaners/<id>` | View / update name | 200 / 404-style error page |
| POST | `/cleaners/<id>/delete` | Delete (rebooks future jobs per rule; abort+report if any job unrebookable) | redirect/error |
| GET/POST | `/clients`, `/clients/<id>`, `/clients/<id>/delete` | Same shape as cleaners; delete cancels client's future jobs, invoices untouched | as above |
| POST | `/jobs/book` | Book job: client_id, cleaners_required ∈ {1,2,3}, hours (>0, ≤9), requested_day (date input) | success: redirect to job page showing assigned cleaners + slot; refusals (length >9 h, no slot) → error message, nothing created (FR-002/003/004) |
| GET | `/jobs`, `/jobs/<id>`, `/jobs/<id>/edit`, POST `/jobs/<id>` `/jobs/<id>/delete` | Job CRUD (edit: client, length, required count → rebooks; delete removes) | 200 / error |
| GET | `/invoices` | List with settled / unsettled status (FR-014) | 200 |
| GET | `/invoices/<id>` | Invoice detail: per-cleaner lines (worked time, $), total, issue moment, payment info | 200 |
| POST | `/invoices/<id>/pay` | amount (decimal). Full-equal → settled; any other amount → refused w/ message; already settled/unknown → refused (FR-013) | as above |
| GET | `/utilization?day=YYYY-MM-DD` | Per cleaner: day worked/8 h, week worked/40 h (FR-015) | 200 |

## Cleaner-facing pages (back-office-rendered, same store)

The cleaner's "local web page expression" is served from the same app so the field loop is testable end-to-end; the Swift package implements the identical rules independently.

| Method | Path | Purpose |
|---|---|---|
| GET | `/field/<cleaner_id>/today` | The cleaner's day: assigned jobs with client, booked times, per-assignment state (FR-006) |
| POST | `/field/<cleaner_id>/jobs/<job_id>/arrive` | Arrive tap (FR-007); invalid → error banner, no change |
| POST | `/field/<cleaner_id>/jobs/<job_id>/depart` | Depart tap; last departure issues invoice (FR-011) |
| POST | `/field/<cleaner_id>/jobs/<job_id>/extend` | +20 min step; cascades rebookings (FR-008/009) |

## Error contract (FR-016)

Every failure returns an HTTP 200 page (redirect-back) carrying a visible error message naming what went wrong (missing record, invalid input, unmet request); **no route emits 5xx for domain refusals**; no record mutated. True server faults are bugs, not contract.

Validation scenarios that exercise every route: see [../quickstart.md](../quickstart.md); rule details: [../data-model.md](../data-model.md) and `shared/rule-spec.md`.
