# Data Model: Cleaning Scheduling and Billing

**Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Entities are identical in both expressions (Python `webapp/cleaning/models.py`, Swift `CleanerApp/Sources/CleaningLogic/Models.swift`), following `shared/rule-spec.md`. IDs are integer sequence numbers per entity type. All times are local, minute-granular (`date`, `time`/datetime at minute precision). Money is Decimal in 2-dp cents (never float).

## Entity: Cleaner

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| name | str | required, non-empty, trimmed |

Relationships: 1 Cleaner — many Job assignments (via `Job.assignments`). CRUD per FR-001. Deleting a cleaner with future jobs triggers rebooking (see State transitions); deletion with no future jobs is plain (edge case). A deleted cleaner is immediately removed from the booking candidate pool.

## Entity: Client

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| name | str | required, non-empty, trimmed |

Relationships: 1 Client — many Jobs; completed jobs keep invoices linked after client deletion (invoices untouched, FR-010). Deleting a client cancels their future `scheduled` jobs.

## Entity: Job

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| client_id | int | required, must exist (FR-002) |
| requested_day | date | required; if weekend/holiday-free, booking moves to Mon (D-3) |
| expected_length_min | int | required, > 0; > 540 (9 h) refused (FR-002) |
| cleaners_required | int | required, ∈ {1, 2, 3} (FR-002) |
| booked_start | datetime | set by booking; on Mon–Fri, ≥ 8:00 (D-3) |
| booked_end | datetime | booked_start + expected_length; ≤ 17:00 unless pushed by extension (FR-008) |
| state | enum | `scheduled` / `in_progress` / `complete` / `cancelled` |
| assignments | list | exactly `cleaners_required` entries — see JobAssignment |
| invoice_id | int? | set at completion, same write (FR-011) |

### Embedded: JobAssignment (per cleaner)

| Field | Type | Rules |
|---|---|---|
| cleaner_id | int | distinct within the job (enough **distinct** free cleaners, FR-003) |
| arrival | datetime? | set by Arrive tap; not before booked_start day |
| departure | datetime? | set by Depart tap; ≥ arrival (same instant allowed → $0.00 line) |
| worked_min | int? | = departure − arrival, derived on Depart (FR-007) |

**Validation rules** (checked on every mutation, whole-operation abort on failure):

- Spacing (FR-005): for any cleaner, no two `scheduled` jobs J1 (earlier) and J2 with J2.start < J1.end + 60 min, symmetrically. Jobs exactly 60 min apart are legal (Assumption).
- Window (FR-004): scheduled jobs inside 8:00–17:00 Mon–Fri; extensions past 17:00 are the sole exemption to the extending job's own end (FR-008); rebooked jobs always inside.
- Tap order: Arrive requires state `scheduled`/`in_progress` with this assignment's arrival unset; Depart requires arrival set, departure unset; otherwise error, no change (FR-016, US2-AC3).

**State transitions**:

```text
scheduled --first Arrive--> in_progress
in_progress --last cleaner Departs--> complete   (+ invoice issued atomically, FR-011)
scheduled --client deleted--> cancelled
scheduled --rebooked--> scheduled (new start/end/cleaners)  # stays scheduled
complete / cancelled --(terminal)--> no transitions
```

Rebooking (extension cascade D-4, delete-cleaner D-5) mutates booked_start/end and possibly assignments; it never applies to `in_progress`, `complete` or `cancelled` jobs (only **future scheduled** jobs participate).

## Entity: Invoice

| Field | Type | Rules |
|---|---|---|
| id | int | unique, system-assigned |
| job_id | int | 1:1 with job, required (FR-012) |
| issued_at | datetime | = moment last cleaner departed (FR-011) |
| lines | list | one per cleaner: cleaner_id, worked_min, amount = round(worked_min/60 × $45, 0.01) half-up |
| total | Decimal | = Σ rounded line amounts (Assumption: total of rounded lines) |
| settled | bool | false at issue (FR-014) |
| payment_amount | Decimal? | set only on full payment (FR-013) |
| payment_date | datetime? | set only on full payment |

**Immutability**: issued invoices never change except `settled`, `payment_amount`, `payment_date`, and only via `record_payment` (FR-010, FR-013). Client/cleaner deletion never touches them (US4-AC4).

## Entity: UtilizationReport (derived view, not stored)

Per cleaner, per reference day D: `day_worked_h = Σ worked_min of assignments with departure on D ÷ 60` shown against 8 h; `week_worked_h` = same over the calendar week containing D, against 40 h (FR-015, D-8). Frames are targets, not caps (Assumption).

## Cross-entity invariants (audit assertions, SC-002)

1. ∀ cleaner, pairwise over their scheduled jobs: gap ≥ 60 min both directions.
2. ∀ scheduled job: 8:00 ≤ start < end ≤ 17:00, Mon–Fri (extending job's post-17:00 end excepted).
3. ∀ complete job ⇔ exactly one invoice, Σ lines total = Σ worked_h × $45 rounded per line.
4. Settled invoice ⇒ payment_amount = total exactly, settled = true.
