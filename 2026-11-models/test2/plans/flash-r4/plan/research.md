# Phase 0 Research: Cleaning Business Scheduling and Billing

Each entry: **Decision** / **Rationale** / **Alternatives considered**. No
NEEDS CLARIFICATION markers were left in Technical Context; every open ambiguity is
already answered in repo-root `questions.md` (re-confirmed here) or resolved below.

## R1. Business timezone and DST handling

- **Decision**: The business's local time is `America/Los_Angeles`, implemented with
  Python `zoneinfo.ZoneInfo` on the desktop and Foundation `TimeZone(identifier:)` on
  mobile. The 8:00–17:00 workday and the quarter-hour grid (anchored at 8:00) are
  wall-clock rules: candidate start/end times are generated as wall-clock local times and
  converted to instants for comparison. Booked parts keep wall-clock times; a part that
  would land on a nonexistent wall-clock time (spring forward) shifts to the next valid
  quarter hour; repeated times (fall back) use the first occurrence, consistent with the
  spec assumption that a booked 8:00–10:00 part occupies the clock span as booked.
- **Rationale**: FR-007 requires local time + calendar clock changes but the problem
  never names the zone; a single US Pacific business is what a careful developer assumes
  for a local 12-cleaner business, and both toolchains ship DST-correct tz databases.
- **Alternatives considered**: UTC-only storage with wall-clock display (rejected — the
  workday/grid/split rules are wall-clock rules, and UTC breaks "starts Monday 8:00");
  configurable-per-install timezone (rejected as an unrequested option, FR-020; kept as
  a constructor default parameter, not a user-facing setting).
- **Owner-confirmation item**: this zone choice is recorded as Q8 in questions.md.

## R2. Money arithmetic and rounding

- **Decision**: Money is integer cents everywhere in stored data; rate $45/h = 4500
  cents/hour. Python computes each line with `Decimal(minutes) * 4500 / 60` and rounds
  with `ROUND_HALF_UP` to the cent; Swift mirrors this on `Decimal`. Golden values:
  3 h 30 min (210 min) → 15750¢ = $157.50; 4 h → 18000¢ = $180.00; total 33750¢ =
  $337.50. The invoice total is the sum of the rounded lines (never rounded from the
  raw sum). Time worked = Depart − Arrive in whole minutes (taps recorded to the
  minute).
- **Rationale**: FR-015 fixes $45/h, per-line half-cent-up rounding, total = sum of
  lines; float dollars would risk sub-cent drift, Decimal-on-minutes is exact until the
  mandated single rounding.
- **Alternatives considered**: binary float dollars (rejected: 0.1-style errors);
  rounding the total from unrounded lines (rejected: violates "total = sum of lines");
  banker's rounding (rejected: spec says half a cent up).

## R3. Overlap definition and the booking scan algorithm

- **Decision**: Two of a cleaner's jobs conflict iff
  `start2 < end1 + 60min` for the earlier-and-later pair (strict `<`, so exactly 1 hour
  apart is allowed: end 12:00 → next 13:00 OK, 12:45 not). The booking rule scans
  day-by-day from the requested day (weekends skipped) for ≤90 calendar days, generates
  each workday's 36 quarter-hour starts (8:00 + 15k, k=0..35), and takes the earliest
  start where the required number N (1–3) of distinct cleaners are free for the part.
  Multi-day split: ceil(hours/8) parts of (8, 8, …, remainder), each booked independently
  on a later *workday* than the preceding part. Prefer the first part's cleaners if free;
  otherwise use other free cleaners. Cleaners are picked in ascending id order among
  qualifying free candidates ("any free cleaners will do") for determinism. No slot in
  the horizon for any part → AppError message, zero writes.
- **Rationale**: FR-003–FR-006 state these rules exactly; deterministic selection (sort
  by id, first-fit) makes tests reproducible and matches "the booking rule may pick any
  qualifying set".
- **Alternatives considered**: interval-merge/booking-calendar data structures (rejected
  as over-engineering at 12 cleaners × 90 days — brute force is provably fast enough);
  least-utilized-first cleaner preference (rejected: spec explicitly does not require
  it); requiring the first part's cleaners for every later part (rejected: the owner's
  split rule allows other free cleaners when the first part's cleaners are not free).

## R4. Extension ("more time") and re-book cascades

- **Decision**: An extension adds one 20-minute step to *that cleaner's* end on an
  arrived, not-yet-departed part (unlimited steps, no 17:00 cap). After each step, any
  later job of that cleaner (or of the extended part's other assigned cleaners — Q1:
  bumped jobs move as a unit, respecting each part's cleaner assignments) starting
  `< new_end + 60min` is un-scheduled and re-booked by the R3 rule with a floor start
  `≥ new_end + 60min`, cascading repeatedly. Cascades use the job-as-unit rule: a new
  slot must satisfy the independent booking rule for each part of the bumped job. Re-books
  beyond the 90-day horizon from the bumped job's original requested day → the whole
  extension operation fails atomically and restores prior schedules (FR-019 all-or-nothing).
- **Rationale**: FR-010/FR-011 + Q1/Q4 answers; all-or-nothing cascade is the only
  reading that satisfies both "never leaves an overlap" (SC-002) and "changes nothing"
  on failure.
- **Alternatives considered**: partial commit of successful cascades (rejected: would
  leave overlaps/dangling schedules); capping extensions at 17:00 (rejected: FR-010
  says extensions may pass 17:00); re-booking only the extending cleaner's own later
  jobs and ignoring co-workers (rejected: contradicts Q1's move-as-a-unit).
- **Owner-confirmation item**: the refuse-the-whole-extension-on-unmeetable-cascade edge
  (beyond Q1's same clause) is recorded as Q9 in questions.md.

## R5. State: shared rule engine across two languages

- **Decision**: The rules are implemented twice — Python in `desktop/cleaning/`, Swift
  in `mobile/Sources/CleaningLogic/` — as structural mirrors (same module names, same
  algorithm, same golden constants) verified by golden example vectors listed in
  contracts/ that BOTH test suites must reproduce. No shared binary, code generation,
  or FFI bridge.
- **Rationale**: FR-018 demands two apps that "follow the same rules" yet are "not
  connected", each with its own file. Duplication with a shared golden-example contract
  enforces behavioral parity without coupling deployment.
- **Alternatives considered**: one engine per app with a spec-derived generated core
  (rejected: build complexity for a 2-app demo); mobile calling the Python engine (hard
  violation of FR-018's disconnection); network sync (out of scope in problem.md).

## R6. Desktop web app framework

- **Decision**: Python stdlib only: `http.server.ThreadingHTTPServer` bound to
  127.0.0.1 with a small JSON-over-HTTP API (`desktop/app.py`), and one vanilla-JS page
  (`desktop/static/index.html`) served by the same process. Requests map to domain
  calls; `AppError` → HTTP 400/404/409 with `{"error": message}` so the page shows the
  message (FR-019). No third-party packages (no FastAPI/Flask).
- **Rationale**: The spec says "a local web page served by Python"; stdlib keeps the
  install to `python3 -m venv .venv` + pytest and honors the no-extra-technology bias.
  Loopback binding matches "local web page, no network services".
- **Alternatives considered**: FastAPI/uvicorn (rejected: extra deps for a single
  single-user page); CGI/static-generation (rejected: needs POST-driven mutations); Tkinter/desktop-GUI
 variants (rejected: spec names a web page).
- **Note**: local HTTP probing on 127.0.0.1 is blocked in this sandbox; the server is
  validated by calling the request handler in-process (WSGI-style probe calls), per
  lessons recorded from prior runs.

## R7. Mobile package: SwiftPM, UI-free, testing

- **Decision**: SwiftPM package `mobile/Package.swift`, one library target
  `CleaningLogic` (Foundation only) + one test target. Public surface = operations
  (`daySchedule(cleanerID:on:)`, `arrive`, `depart`, `extend(by:)`, CRUD, invoices,
  utilization) on a `CleaningApp` class parameterized by data-file URL and timezone;
  everything throws typed `AppError`. Tests run `swift test --disable-sandbox` (this
  host rejects SwiftPM's nested sandbox). The runner supplies cleaner identity — no
  accounts (Q6).
- **Rationale**: problem.md fixes the deliverable as "a Swift package holding the app's
  logic, with no user interface". XCTest via SwiftPM is the only test harness available
  (Xcode-less CLI).
- **Alternatives considered**: UIKit/SwiftUI target (forbidden by the spec); XCTest UI
  tests (no UI); Core Data (rejected: plain JSON file per R8 keeps the two stores
  symmetric).

## R8. Persistence and atomicity

- **Decision**: One JSON file per app (`desktop/data.json`; the mobile data file lives
  beside the mobile app's own container/dir given by its caller). Every mutating
  operation: load → validate → mutate an in-memory model copy → serialize → write temp
  file → atomic rename over the data file, all under one process-level lock. On any
  error before the rename, nothing has been published (FR-019 "apply no changes"). File
  layout and record shapes are identical in both apps (same Key Entities), differing
  only in language. IDs are server-issued monotonic integers (cleaner/client/job/invoice)
  and composite `job_id:part_index:cleaner_id` keys live inside job records.
- **Rationale**: FR-018/FR-019 require local-file persistence across restarts with
  all-or-nothing operations; write-temp+rename is the portable cheap atomic write.
- **Alternatives considered**: SQLite (rejected: two more formats to mirror across
  languages for ~34 records, and FR-020's minimalism); append-only log + compaction
  (rejected as unneeded durability ceremony); autosave-per-mutation without a lock
  (rejected: risk of torn reads under ThreadingHTTPServer).

## R9. Validation of free-text and CRUD edges

- **Decision**: Names, addresses, phones, notes are stored as supplied; the only field
  validations are type/presence checks (non-empty strings, numeric positive length,
  1–3 cleaners, valid ids). Unknown id on read/update/delete → AppError("… does not
  exist"), no change, app continues. Delete guards: job with issued invoice refused;
  cleaner delete re-books their future jobs (nobody arrived) via the booking rule with
  any free cleaners; client delete cancels their future jobs (status `cancelled`,
  arrived-at jobs untouched). No duplicate detection (Q6).
- **Rationale**: spec Assumptions say exactly this; SC-001/SC-005 only require
  no-crash + message + no-change.
- **Alternatives considered**: soft-delete + audit trail (unrequested); duplicate-name
  warnings (out of scope); hard-deleting records that invoices reference (rejected:
  FR-013 immutability of issued invoices demands retaining their cleaner/time data by
  embedding line data in the invoice itself, which we do — invoices snapshot
  cleaner name/time/amount at issue time).

## R10. Utilization computation

- **Decision**: From tap pairs only (R2 minutes). Per cleaner, per local calendar day:
  sum of overlaps of each worked interval [arrive, depart) with that day, reported as
  `hours / 8` (may exceed 8). Per Mon–Sun ISO-style week anchored on the work week
  (Monday) summing the same minute-level day-overlap slices, `/40` (may exceed 40).
  Interval splitting uses zone-aware instants so a 22:00–02:00 span yields exactly 2 h
  and 2 h; overnight weeks split similarly. No-arrive → 0 worked hours.
- **Rationale**: FR-017 and SC-007 state the split rule and 2/2 example directly.
- **Alternatives considered**: assigning the whole span to its start day (violates the
  example); capping at 8/40 (violates "may exceed"); using booked schedule instead of
  taps (spec says billable hours worked = tap-to-tap).

## Post-Design Re-check (Constitution Check, after Phase 1)

Re-evaluated against FR-020/FR-018/FR-019 after producing data-model.md, contracts/ and
quickstart.md: the design adds no domains, rules, screens, notifications, due dates,
holidays, or connectivity beyond spec + questions.md assumptions; issued-invoice
snapshots are data retention required by FR-013, not new entities. **Result: PASS.**
