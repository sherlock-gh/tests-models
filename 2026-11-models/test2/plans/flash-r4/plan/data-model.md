# Data Model: Cleaning Business Scheduling and Billing

Entities mirror spec.md's Key Entities. Both apps store the identical shapes in their own
single JSON file (`desktop/data.json`; mobile file at the caller-supplied path). IDs are
integers issued by the app that owns the file, monotonically increasing per entity type
per file; deleted IDs are never reused. Times in stored records are **local wall-clock
strings** (`YYYY-MM-DDTHH:MM`, business zone = America/Los_Angeles, Q8) except tap
instants, which are stored as `YYYY-MM-DDTHH:MM` local wall-clock too (recorded to the
minute, FR-008) — elapsed math converts to instants. Money is integer cents (research
R2). Enumerated values are exact JSON strings below.

## Cleaner

| Field | Type | Rules |
|---|---|---|
| id | int | system-issued, unique in file |
| name | str | non-empty; stored as supplied, no duplicate detection (Q6) |
| phone | str | non-empty; as supplied |
| email | str | non-empty; as supplied |
| active | bool | false only conceptually — deletion is the real removal; kept true always in v1 |

Utilization is **derived**, not stored (see Utilization below).

## Client

| Field | Type | Rules |
|---|---|---|
| id | int | system-issued, unique |
| name | str | non-empty; as supplied |
| address | str | non-empty; as supplied |
| phone | str | non-empty; as supplied |

## Job

| Field | Type | Rules |
|---|---|---|
| id | int | system-issued, unique |
| client_id | int | must reference an existing Client (dangling id → AppError, no crash) |
| cleaners_needed | int | 1, 2 or 3 (FR-002) |
| expected_length_hours | number | > 0; not necessarily whole (edge: 4.5 → parts 4.5 in one day) |
| requested_day | date str `YYYY-MM-DD` | booking searches on/after this day, ≤ 90 days past it (FR-006) |
| status | enum | `booked` \| `cancelled` (cancelled only via client deletion, FR-012) |
| parts | list[JobPart] | 1+ parts; ceil(len/8) parts, with each subsequent part independently booked on a later workday, preferring first-part cleaners when free, otherwise other free cleaners (FR-005) |
| invoice_id | int \| null | set at completion (FR-014); blocks job deletion (FR-013) |

A job is **future** iff no assignment on any part has an arrive tap (FR-012). A job is
**complete** iff every assignment on every part has a depart tap (a 0-tap cleaner is
impossible: depart requires arrive; a never-arrived cleaner keeps the job incomplete —
Q3/spec assumption).

## JobPart (embedded in Job.parts; not independently addressable)

| Field | Type | Rules |
|---|---|---|
| part_index | int | 0-based, consecutive |
| day | date str | first part on/after requested day; subsequent parts on later **workdays** (Mon–Fri), each independently booked |
| start | `YYYY-MM-DDTHH:MM` | quarter-hour grid from 8:00 (minute ∈ {0,15,30,45}); ≥ 8:00 |
| end | `YYYY-MM-DDTHH:MM` | start + part length; ≤ 17:00 for booked parts; extension may push an individual cleaner's effective end past 17:00 (stored on Assignment) |
| assignments | list[Assignment] | exactly one per assigned cleaner; `cleaners_needed` distinct cleaners on each part, with first-part cleaners preferred if free |

## Assignment (embedded in JobPart.assignments — pairs cleaner to job part, FR spec)

| Field | Type | Rules |
|---|---|---|
| cleaner_id | int | references Cleaner; may differ across parts if first-part cleaners are not free (FR-005) |
| arrive | `HH:MM`-bearing local str \| null | recorded to the minute; second Arrive refused (Q5) |
| depart | local str \| null | requires prior arrive for this cleaner on this job (Q5); depart < arrive refused |
| extended_minutes | int | ≥ 0, multiple of 20 (FR-010); only while arrived & not departed; this cleaner's effective part end = part end + extended_minutes (extensions past 17:00 allowed) |

Time worked (per cleaner per job) = Σ over parts of (depart − arrive) in whole minutes
(FR-009). Extensions change schedules and later-job spacing, and lengthen worked time
only through actual later taps (worked time is always tap-to-tap, spec Assumptions).

## Invoice

| Field | Type | Rules |
|---|---|---|
| id | int | system-issued, unique |
| job_id | int | the completed job (1 invoice per job) |
| issued_at | local str | moment of last depart tap (FR-014) |
| lines | list[InvoiceLine] | one per distinct cleaner assigned to any part, with their time summed across their parts; see below |
| total_cents | int | = Σ lines[].amount_cents exactly (R2) |
| settled | bool | false until an exact payment (FR-016) |
| payment | Payment \| null | the single settlement payment, embedded |

Immutability (FR-013): once issued, no mutation or delete path touches an invoice;
invoices snapshot cleaner name/time/amount so referenced-record deletion can't alter them.

### InvoiceLine (embedded)

| Field | Type | Rules |
|---|---|---|
| cleaner_id | int | snapshot |
| cleaner_name | str | snapshot at issue time |
| minutes_worked | int | tap-to-tap total (R2) |
| amount_cents | int | Decimal(minutes)*4500/60 rounded ROUND_HALF_UP (4500¢/h = $45/h) |

## Payment (embedded in Invoice.payment)

| Field | Type | Rules |
|---|---|---|
| amount_cents | int | must == invoice.total_cents exactly; any other amount is refused and never stored (FR-016) |
| paid_at | local str | recorded minute |

## Utilization (derived view, never stored; computed from assignments)

Per cleaner:
- **per local calendar day**: Σ overlap([arrive, depart) with that day) in minutes,
  reported as `hours / 8` — may exceed 8 (FR-017); 22:00–02:00 → 120 + 120 min split.
- **per Monday–Sunday week**: Σ of the same minute slices grouped by ISO-style week
  anchored Monday, reported as `hours / 40` — may exceed 40.

## State transitions

- Job: (created) → `booked` (booking rule placed all parts) | refused (message, no
  record, FR-006). `booked` → `cancelled` only when its client is deleted while it is a
  future job (FR-012). Arrived-at jobs survive client deletion unchanged.
- Assignment taps: `(null, null)` → *(arrive)* → `(t1, null)` → *(depart)* →
  `(t1, t2)`; depart ends accrual (US2-AC3). Illegal transitions (second arrive, depart
  without arrive, depart < arrive, extend after depart) → AppError message, no change
  (Q5). Extend from `(t1, null)`: extended_minutes += 20, cascading re-books (FR-011).
- Cleaner deletion: future jobs of that cleaner are re-booked by the booking rule with
  any free cleaners (assignments replaced), then the cleaner record is removed
  (FR-012/US5-AC1). Client deletion: their future jobs → `cancelled`; client record
  removed. Job deletion: refused iff invoice_id set (FR-013).
- Invoice: absent → issued (instant of last depart, one shot) → settled (one exact
  payment). No other transitions; issued invoices are terminal artifacts (FR-013).

## Cross-entity validation rules (enforced on every mutation, each an atomic unit)

1. No cleaner ever has two jobs (parts) where the later starts `< earlier_end + 60min`
   (strict), including effective ends after extensions (FR-004, FR-011, SC-002).
   Extended assignments ignore the ≤17:00 bound; booked parts must respect it.
2. Booking/re-booking searches start days from anchor day forward ≤ 90 days, weekdays
   only; no slot → AppError, zero writes (FR-006; Q9 for cascades).
3. Every part start lands on the 8:00-anchored quarter-hour grid; parts of one job
   have `cleaners_needed` distinct cleaners each, with the first part's cleaners preferred
   when free and other free cleaners otherwise; each later part is independently booked
   on a later workday (FR-003/FR-005).
4. Unknown ids, bad lengths (≤0 hours, needed ∉ {1,2,3}), malformed times/amounts →
   AppError message, nothing changed, app keeps working (FR-019, FR-001).
5. Files per research R8: one JSON file per app holding {cleaners, clients, jobs,
   invoices, counters}; atomic temp+rename write under a lock.
