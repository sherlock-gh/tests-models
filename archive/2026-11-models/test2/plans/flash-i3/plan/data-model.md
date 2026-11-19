# Data Model: Cleaning Business Scheduling and Billing

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

Both apps model the same entities with the same rules (research.md R4–R7). Types are given
language-neutrally; the Python app expresses them as dataclasses and the Swift package as
structs. Money is integer cents everywhere (R2). Times are local wall-clock `HH:MM` on a
`YYYY-MM-DD` date in the business's time zone (R3). IDs are positive integers assigned per
collection from a stored `seq` counter.

## Entity: Cleaner

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| name | str | required, non-empty after trim |

Availability is fixed: every cleaner works 8:00–17:00, Monday–Friday (the problem states no
individual variation — inventing availability rules is forbidden by FR-017). Deleting a
cleaner triggers rebooking of their future jobs (see State Transitions / R7).

## Entity: Client

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| name | str | required, non-empty after trim |

Deleting a client cancels their future jobs (R7).

## Entity: Job

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| client_id | int | must reference an existing Client |
| cleaners_needed | int | 1, 2 or 3 (1–3 cleaners per job, FR-002) |
| expected_length_min | int | > 0, minutes; population mean ≈ 248 min (4.14 h), SD ≈ 105 min (1.75 h) — data description, not a validation rule |
| requested_day | date | day back office asked for; booking search starts here |
| cleaner_ids | list[int] | length == cleaners_needed; assigned by the system ("assigns the cleaners itself", FR-002); updated on cleaner deletion (R7) |
| parts | list[JobPart] | ≥ 1; a job > 8 h splits into `floor(L/480)` 480-min parts + remainder part on consecutive workdays, same cleaners on every part (FR-006, R5) |
| status | enum | `booked`, `in_progress`, `complete`, `cancelled` (see state machine) |
| invoice_id | int? | set the moment the job completes (FR-013); blocks deletion (FR-012) |

A job is a **future job** iff **no cleaner has tapped Arrive on it yet** (FR-011) —
i.e. status == `booked` — evaluated at the moment of the deleting/rebooking operation.
A **part** of an in-progress job may exist on a later workday; the whole job is what is
rebooked or cancelled as a unit.

## Entity: JobPart

| Field | Type | Rules |
|---|---|---|
| start_day | date | a weekday; consecutive workdays across a split job's parts |
| start_min | int | minutes since midnight; on the quarter-hour grid (`start_min % 15 == 0`) and >= 480 (8:00) for booked parts, FR-003; every part of a split job starts at 480 (R5) |
| end_min | int | start_min + part length; for **booked** parts `end_min <= 1020` (17:00) — "a booked job starts and ends within those hours" (FR-005). Extension-applied parts may exceed 1020; an extension may cross midnight, moving tail minutes to the next day's utilization (R6/R10) |
| duration_min | derived | end_min - start_min (>= 0 on the wall grid) |

Shadow rule (FR-007): for the same cleaner, part B of another job overlaps when
`B.start_instant < A.end_instant + 3600s`. Booking, extension and rebooking must never leave
this true. Boundary pins: end 12:00 → next start >= 13:00 (12:45 refused); end 12:10 → next
start 13:15 (first quarter hour at least an hour later).

## Entity: Tap

| Field | Type | Rules |
|---|---|---|
| job_id | int | referencing Job |
| cleaner_id | int | one of the job's assigned cleaners |
| kind | enum | `arrive` or `depart` |
| instant | datetime | recorded **to the minute** (seconds truncated; FR-008) |

Per-cleaner time worked = (depart instant - arrive instant) in whole minutes. Tap rules:
Arrive requires status `booked`/`in_progress` and the job's (first) part started (not in the
future for this cleaner); a second Arrive before Depart is refused; Depart without a prior
Arrive is refused — both show an error and change nothing (edge cases).

## Entity: Invoice

| Field | Type | Rules |
|---|---|---|
| id | int | unique |
| job_id | int | the completed job |
| issued_at | datetime | the moment the last cleaner departed (FR-013) — "issued at that moment" |
| lines | list[InvoiceLine] | one per assigned cleaner, "lists each cleaner's time" |
| total_cents | int | = sum of line cents (never re-derived from unrounded values) |

**InvoiceLine**: `cleaner_id`, `minutes_worked` (int, to the minute), `cents` =
`round_half_up(minutes_worked * 4500 / 60)` at $45/hour (4500 cents/h; research R2).
Immutable after issue: "Issued invoices never change and are never deleted" (FR-012); any
update/delete attempt is refused with a message.

## Entity: Payment

| Field | Type | Rules |
|---|---|---|
| id | int | unique |
| invoice_id | int | must exist |
| amount_cents | int | > 0 |
| paid_at | datetime | recording time |

Creation succeeds **only** when the invoice is unsettled and `amount_cents ==
invoice.total_cents` — "paid in full in one payment"; every other amount (over, under,
partial, a second payment) is refused with the invoice unchanged (FR-014). The accepted
payment is the settlement record; settled state is derived from its existence.

## Entity: UtilizationReport (derived, not stored)

Per cleaner for a day D: `hours = tapped minutes on D / 60` reported "out of 8"; for a
Monday–Sunday week W: sum of the seven days, reported "out of 40". Work past midnight
splits at 00:00 local ("counts on each day for the part worked that day", FR-015; e.g.
22:00–2:00 → 2 h each day). Values may exceed 8/40 (45 h shows as 45 of 40). Only tapped
(Arrive→Depart) time counts — booked-but-no-show time never does (spec Assumption), and a
cleaner with no taps yields 0 hours, not an error.

## Relationships

- Client 1—N Job (`client_id`); deleting Client ⇒ cancel its future jobs (booked status),
  jobs otherwise remain for history.
- Cleaner N—N Job via `cleaner_ids` (1–3 per job, system-assigned). Deleting Cleaner ⇒
  rebook their future jobs with any free cleaners; in-progress jobs keep running minus the
  deleted cleaner (R7, questions.md Q2/Q6).
- Job 1—N JobPart (>= 1, consecutive workdays when split, same cleaners on every part).
- Job 1—N Tap (2 per cleaner per part-worked: Arrive, Depart, to the minute).
- Job 1—0..1 Invoice (issued at last departure); Invoice 1—0..1 Payment (one full-total
  payment).

## Job State Machine

```text
booked ──(first cleaner taps Arrive)──▶ in_progress
booked ──(client deleted)──▶ cancelled            [client deletion, FR-011]
booked ──(back office deletes job)──▶ (removed)   [no invoice, FR-001]
booked ──(cleaner deleted / extension cascade)──▶ rebooked by the booking rule with the
        search floor at the trigger time (still 'booked'; R6/R7, Q2)
in_progress ──(every assigned cleaner has departed)──▶ complete   [invoice issued now, FR-013]
```

- `complete` is terminal; its invoice id is set in the same atomic write (SC-004).
- `in_progress` and `complete` jobs are not moved by rebooking: "an already-arrived job is
  never moved" (edge case), and deletion of their cleaner leaves them untouched except for
  the crew-list removal (R7).
- Extensions apply only on `in_progress` jobs by a cleaner who has tapped Arrive and not
  departed; any other request is refused (FR-009, US3 AC5).

## Validation summary (all failures: show message, change nothing, keep running — FR-016)

- cleaners_needed outside 1–3; expected_length_min <= 0; unknown client/cleaner/job id;
  blank name.
- Booking with no slot by requested_day + 90 days ⇒ refusal message (FR-004).
- Arrive twice, Depart without Arrive, extension before Arrive / after Depart.
- Delete job with an issued invoice; update/delete an issued invoice.
- Payment != exact unsettled total, payment on settled/unknown invoice.

