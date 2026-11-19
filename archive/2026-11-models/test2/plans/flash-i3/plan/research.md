# Phase 0 Research: Cleaning Business Scheduling and Billing

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Every decision below traces to problem.md / spec.md text. Where problem.md is silent, the
decision matches a recorded answer in `/questions.md` (Q1–Q6) and is marked accordingly.
No NEEDS CLARIFICATION markers remain.

## R1 — Language, dependencies, and test harness per app

- **Decision**: Python 3.12+ with the standard library only (`http.server`/`wsgiref`,
  `json`, `decimal`, `zoneinfo`, `unittest`), tests run with `pytest`. Swift 6.1 SwiftPM
  library with Foundation only, tested with `swift test` (XCTest). Both verified present on
  this host (Python 3.14.7, Swift 6.1.2).
- **Rationale**: problem.md prescribes exactly the two forms — "a local web page served by
  Python" and "a Swift package holding the app's logic, with no user interface". The rule
  set is small (one workday grid, one shadow rule, one rate); no framework earns its
  dependency. Stdlib `decimal`, `zoneinfo` and `json` cover the only hard parts (cent
  rounding, clock changes, persistence).
- **Alternatives considered**: FastAPI/Flask (third-party, adds install surface, no benefit
  for a 2-user local page); SQLite (problem.md says "its data in its own local file" and
  the entities are tiny — a JSON file is simpler and diffable); Swift Charts / UIKit (UI is
  out of scope); shared rules via a C core or code generation (the apps "are not
  connected"; duplication + shared contract tests is what the spec describes).
- **On this host**: `swift build`/`swift test` must run with `--disable-sandbox`
  (SwiftPM's nested sandbox is denied here).

## R2 — Money: integer cents and half-up rounding

- **Decision**: All money lives in integer cents. Rate = 4500 cents/hour = exactly 75
  cents/minute, so tapped minutes never produce a fraction of a cent — but the half-up rule
  is still implemented explicitly. A cleaner line = `round_half_up(minutes × 4500 ÷ 60)`,
  computed as `Fraction(minutes*4500, 60)` in Python (or `Decimal` quantized with
  `ROUND_HALF_UP`), never as a binary float; in Swift as integer arithmetic
  `(minutes * 4500 + 30) / 60`. Invoice total = sum of the rounded line values.
- **Rationale**: FR-013 fixes $45/h, taps to the minute, lines "rounded to the nearest
  cent, half a cent up", total = "sum of lines" (not re-rounded from unrounded sums).
  Because 4500/60 = 75 is exact, no minute value can land on a half cent; a float pipeline
  would still risk 0.1-class drift, so amounts stay integer cents end to end and dollars
  are formatted only at the edge. Golden values:
  3 h 30 min = 210 min → **15750 cents** ($157.50); 4 h → **18000 cents** ($180.00);
  the same two cleaners on one invoice → **33750 cents** ($337.50). Payment compares cents
  for exact equality (FR-014).
- **Alternatives considered**: float dollars (rejected: 0.1-class errors and half-cent
  ambiguity); rounding the total from summed unrounded amounts (rejected: FR-013 says the
  total is the sum of the *rounded* lines); banker's rounding (rejected: the spec says half
  a cent up).
- **Swift note**: `Decimal.rounded()` defaults must not be trusted here; the integer
  `(minutes * 4500 + 30) / 60` form is pinned by a test so both apps agree to the cent.

## R3 — Time grid: quarter-hour starts, workdays, shadow, and DST

- **Decision**: Times are stored and computed as `YYYY-MM-DDTHH:MM` local wall-clock
  strings in the business's time zone, which the environment names for each app (this host:
  `America/Los_Angeles`); Python resolves them with `zoneinfo.ZoneInfo`, Swift with
  `TimeZone(identifier:)`. The booking day-grid is the quarter-hour sequence 8:00, 8:15, …
  inside Monday–Friday 8:00–17:00. Overlap test: job B overlaps job A for the same cleaner
  iff `B.start < A.end + 60 min`; a candidate start must therefore be >= A.end + 60 min
  **and** land on the grid (end 12:00 → next 13:00 allowed, 12:45 not; end 12:10 → next is
  13:15). Comparisons are done on UTC instants (DST-safe: adding 60 minutes means adding
  3600 real seconds); rendering back to wall clock uses the zone, so the 15-minute
  floor/round-up happens on local wall time as the examples state.
- **Rationale**: FR-005 ("Times are the business's local time, and the calendar's clock
  changes apply") plus the 12:00/12:10 examples. DST ambiguity is handled by converting to
  instants for arithmetic and by never booking outside 8:00–17:00 local, so the 1 a.m.
  fold/spring-forward hour never enters a booking window. Weekend and pre-8:00 requests
  clamp to Monday 8:00 that week / same-day 8:00 per spec Assumptions.
- **Alternatives considered**: naive local datetimes (rejected: DST arithmetic errors on
  the two change-days per year); integer minutes since midnight without a zone (rejected:
  FR-005 makes clock changes normative); UTC storage (rejected: all rules including
  8:00–17:00 and quarter-hour grid are wall-clock rules).

## R4 — Booking algorithm (earliest slot, 90-day search, >8 h split)

- **Decision**: Booking a job with `n` (1–3) cleaners needs and requested day `D`:
  1. Walk days D, D+1, … (calendar days; Sat/Sun and pre-8:00 clamp per R3) up to and
     including D+90.
  2. On each day, walk the quarter-hour grid from the first allowed start.
  3. At each candidate start, find `n` cleaners free for *every* part of a split job
     (parts per R5). "Free" = the candidate part (start, end) respects the 1-hour shadow
     against each of that cleaner's non-cancelled booked parts.
  4. First day-and-time where `n` free cleaners exist wins; assign the first `n` free
     cleaners in stable id order, create the parts. If no day within D..D+90 works, refuse
     with the message "No slot for this job within 90 days of the requested day." and
     change nothing.
  Search exhaustiveness note: on a 12-cleaner, single-window grid, if any valid placement
  exists for this job shape there is one at a quarter-hour start on some day in the window
  (parts are contiguous blocks inside 8:00–17:00 on consecutive workdays), so day-major,
  time-minor scanning finds the earliest slot as specified. The scan is run against a
  working copy of the store and committed only on success (FR-016: nothing changes on
  refusal).
- **Rationale**: FR-002/003/004 verbatim — earliest slot on or after the requested day,
  "Any free cleaners will do" (so first-fit by id, no optimization), 90-day cap with
  refusal, atomicity from FR-016/SC-003. Average length 4.14 h / SD 1.75 h describes the
  data, not a rule — no code depends on it.
- **Alternatives considered**: optimizing cleaner choice by proximity/utilization (rejected:
  "Any free cleaners will do", and inventing preferences would add rules FR-017 forbids);
  interval-tree indexing (rejected at this scale — brute force over ≤91 days × 36 slots ×
  12 cleaners is trivially fast); refusal as an exception (rejected: must be a shown
  message + unchanged store).

## R5 — Splitting jobs longer than 8 hours

- **Decision**: A job with expected length `L > 8 h` becomes `floor(L/8h)` parts of 8 h
  plus one final part of the remainder (`L mod 8h`, when non-zero), on **consecutive
  workdays** (part k on the k-th consecutive workday from the first placed part), the same
  `n` cleaners on every part. Every part starts at **8:00** on its workday (8:00–16:00 for
  an 8 h part; 8:00–8:00+rest for the final part), which is the only start that satisfies
  "as many 8-hour parts as it needs, then the rest" inside one 8:00–17:00 window given the
  crew's other bookings are checked per part. If the chosen crew is not all free for one
  part's block (their 1-hour shadow says no), the whole split candidate fails and the
  search moves on — the job moves as a unit. `L ≤ 8 h` is one part booked by the ordinary
  booking rule (problem example: a 10-hour job → 8 h day 1 + 2 h day 2; an 8 h job fits one
  day 8:00–16:00). (Decision follows questions.md Q1.)
- **Rationale**: FR-006 plus the problem's boundary examples. Fixing parts at 8:00 is the
  reading consistent with "consecutive workdays" and the 10-hour example; alternatives
  allowed no placement at all for the "rest" part after an 8 h part under shadow rules.
- **Alternatives considered**: each part searched independently for its own earliest slot
  (rejected: breaks "consecutive workdays" and can split parts across a weekend gap
  non-consecutively in ways the example contradicts); two cleaners booked with staggered
  part times (rejected: shadow rule of R3 would still push parts to unique times and no
  earliest-slot meaning survives).

## R6 — Extensions (more time) and the rebooking cascade

- **Decision**: `requestMoreTime(cleanerId, jobId)` is valid only when that cleaner has
  tapped Arrive on the job and has not departed (else refused with an error, nothing
  changes); each call adds 20 minutes to that cleaner's job end (job end = max over its
  cleaners' expected work window — the extension extends the job's scheduled end and the
  requesting cleaner's schedule). No cap; it may pass 17:00 (Q3). After the extension
  lands, examine the cleaner's **future jobs** (nobody tapped Arrive) whose start falls
  `< 60 min` after the new end; rebook each such job by the booking rule with the earliest
  slot **starting no earlier than newEnd + 60 min** (same crew of a future job stays
  together — it has never been staffed inconsistently; parts re-split if the new start
  changes day structure). Rebooking a job can push it into another future job's shadow →
  cascade, repeating until no overlap exists. Already-arrived jobs are never moved; jobs of
  *other* cleaners are only touched when they share the extended job's rebooked future
  jobs (shared-crew), and the cascade keeps them overlapping-free. The whole cascade runs
  on a working copy and commits atomically; if any step cannot place a job within its
  90-day window, the **entire extension is refused with a message and nothing changes**
  (FR-016 "changes nothing" applied to the operation as a unit).
- **Rationale**: FR-009/FR-010 verbatim, including "as many as needed", "may run past
  17:00", "starting no earlier than 1 hour after the extended job's new end", "A job that
  this bumps is booked again the same way". Atomic all-or-nothing matches SC-003.
- **Alternatives considered**: capping extensions at 17:00 or midnight (rejected: spec says
  as many as needed / past 17:00 allowed, and Q3 records the no-cap reading — the 22:00–2:00
  utilization example presumes overnight work exists); partial commit of a failed cascade
  (rejected: would leave overlaps, violating FR-007/SC-002); moving already-arrived jobs
  (rejected: spec — only future jobs get bumped).

## R7 — Deletions: rebooking, cancellation, invoice immutability

- **Decision**: "Future job" = a job nobody has tapped Arrive on (FR-011), evaluated at
  deletion time.
  - **Delete cleaner**: remove the cleaner; every future job they are on is rebooked by the
    booking rule (R4) with any free cleaners — the deleted cleaner is simply no longer
    available, and a multi-part job's future parts rebook as a unit (Q2: the "same crew"
    rule yields to the deletion rule). Jobs already arrived-on/completed keep existing
    (Q6): the deleted cleaner is removed from the crew of in-progress jobs, which then
    complete and invoice on the remaining cleaners' departures, listing only remaining
    cleaners' lines; already-issued invoices survive untouched.
  - **Delete client**: remove the client and **cancel** all their future jobs (cancel =
    status `cancelled`, jobs stay visible, no rebooking, they leave every cleaner's
    schedule and shadow book).
  - **Delete job**: allowed while not invoiced; refused with a message once its invoice has
    been issued (FR-012). Deleting an unstarted job simply frees its slots.
  - **Issued invoices** are immutable: no update, no delete, ever (FR-012); attempted
    mutations are refused with a message, nothing changes.
  - Records that don't exist, or bad input (name empty, n not in 1–3, length ≤ 0
  or > 90-day cap inputs): error shown, nothing changes (FR-016).
- **Rationale**: FR-001/FR-011/FR-012 plus edge cases; the cancellation-vs-rebooking split
  is exactly what the spec assigns to client-vs-cleaner deletion.
- **Alternatives considered**: rebooking a deleted client's jobs to a placeholder client
  (rejected: spec says cancel); hard-deleting jobs (only invoiced jobs are pinned —
  unstarted un-invoiced jobs may be deleted outright per FR-001 CRUD); cascading cleaner
  deletion into cancel (rejected: spec says rebook).

## R8 — Persistence: one JSON file per app, atomic rewrite

- **Decision**: Each app owns one local JSON file with the whole document
  (`{cleaners, clients, jobs, invoices, payments, seq}`; schema in
  [data-model.md](data-model.md)). Desktop default `desktop/data.json` (overridable via
  `CLEANING_DATA` env var); the Swift package takes a `fileURL:` from its caller so tests
  use temp files. Every successful operation rewrites the file via temp-file + `rename`
  (POSIX atomic replace); reads happen at operation start. The two files are never read by
  the other app — "the two are not connected" is enforced structurally: zero shared paths,
  zero sync code.
- **Rationale**: FR-001 ("each app keeps its records in its own local file"), Known limits
  (no services). At 2+12 users with one operation per user action, whole-file rewrite is
  simplest and gives trivially atomic commits (write validation happens before write, so
  FR-016's "changes nothing" is file-level, not in-memory-only).
- **Alternatives considered**: SQLite (still "a local file" but adds query layer, migrations
  and a writer each side for no need at this scale — rejected under FR-017 minimalism);
  append-only log + compaction (more machinery than needed); per-entity files (invites
  torn writes across files).
- **On-disk corrupt file**: on load, an unreadable/invalid JSON file is an error shown to
  the user; the app refuses to start the operation and changes nothing (back up the file
  manually). No silent re-initialization, which would destroy data.

## R9 — Error handling and UI behavior (FR-016)

- **Decision**: Rule functions are pure over a working copy: validate → mutate copy →
  persist. Errors are values (`Error(code, message)` in Swift; Python raises internal
  `RuleError(message)` caught at the boundary). The HTTP layer converts every `RuleError`
  to a JSON response `{"error": message}` with status 400 (404 for unknown-record reads)
  and never propagates an exception to the server log-crashing path; the browser page shows
  the message in an error banner. The Swift package returns `Result`/throws typed
  `CleaningError` so the (future) UI can surface the message. Unknown HTTP routes, bad
  JSON bodies, missing fields → same error envelope. After any error the app stays up and
  the file is unchanged.
- **Rationale**: SC-003 ("doesn't crash ... shows the error ... carries on working")
  requires boundary-level interception, not per-call try/except luck. Pure-copy mutations
  give "changes nothing" for free.
- **Alternatives considered**: letting exceptions bubble to a framework debugger page
  (rejected: crashes the request and leaks internals); partial mutation then rollback via
  undo log (rejected: copy-then-swap is simpler and identical in effect at this scale);
  toast/notification UX (rejected as an invented rule — only "shows the error").

## R10 — Utilization report (per day out of 8, per Mon–Sun week out of 40)

- **Decision**: Billable minutes for a cleaner day D = sum over their tap pairs
  (Arrive→Depart) of the minutes that fall within calendar day D in local time; a tap span
  crossing midnight splits at 00:00 local and contributes to both days (22:00→02:00 →
  120 min each day). Daily report = minutes/60 shown "out of 8"; weekly report sums the
  seven Mon–Sun days of the containing week "out of 40". No caps: 45 h shows as 45/40.
  Cleaner with no taps in the period → 0 hours, not an error (US6 AC4). Only tapped time
  counts (spec Assumption); booked-but-no-show time never does. Weekend tap minutes still
  count on their day and in the Mon–Sun week total (Q4).
- **Rationale**: FR-015's wording is day-of-work attribution of worked minutes, not
  workday-window clipping — the 22:00–2:00 example pins this. Monday-start weeks are stated
  explicitly in FR-015.
- **Alternatives considered**: clipping all work into 8:00–17:00 (rejected: contradicts the
  midnight-spanning example); attributing a past-midnight span wholly to its start day
  (rejected: spec says "counts on each day for the part worked that day"); capping at 8/40
  (rejected: "may exceed").

## R11 — Desktop web page (served by Python)

- **Decision**: `desktop/server.py` runs `wsgiref.simple_server` on `127.0.0.1:$PORT`
  (default 18080 in the demo; Procfile `web:` line uses `$PORT`/`$DATA`) serving
  `desktop/static/index.html` at `/` and a JSON API at `/api/...` (see
  [contracts/desktop-api.md](contracts/desktop-api.md)). The single page is vanilla
  HTML+JS: forms for cleaner/client CRUD, a booking form, day/week utilization, invoice
  list with settled/unsettled grouping and a pay box, and a job list with delete buttons.
  Fetch responses with `{"error"}` render into a page-level error banner. Server stays
  running; per-request store reload lets two staff's tabs each see committed state
  (independent, not synced, last-write-wins on whole-file rewrite — acceptable for 2
  trusted local users on synthetic data).
- **Rationale**: problem.md prescribes "a local web page served by Python" and nothing
  more; no JS framework, no build step keeps the app inspectable and honest to FR-017.
- **Alternatives considered**: Flask/FastAPI + Jinja (dependency for no rule-enforcement
  value); a CLI (spec says web page); WebSockets live sync (rejected: "the two are not
  connected" and sync-out-of-scope).

## R12 — Seed data and synthetic fixtures

- **Decision**: Both apps start with an empty store (no cleaners). Tests (and the quickstart
  demo) seed synthetic data: 12 cleaners with distinct ids/names, several clients, jobs
  whose lengths hover at ~4.14 h mean / ~1.75 h SD exactly as needed per scenario (e.g.
  1 h, 3.5 h, 8 h, 10 h). A tiny `seed_demo()` helper in each app inserts a fixed synthetic
  fixture set; no randomness in tests (deterministic pins: fixed dates in a known week,
  e.g. Mon 2026-11-16). No holidays, no cleaner availability variation (all available
  8:00–17:00 Mon–Fri) because the problem states none.
- **Rationale**: every number in tests must be checkable against problem.md's examples;
  random generators would make golden assertions impossible. The 4.14/1.75 stats describe
  the population in the problem, so fixtures are drawn to average near those without any
  rule depending on it.
- **Alternatives considered**: random data generation with statistical assertions (rejected:
  flaky vs SC-002's exactness); importing a shared fixture file across apps (rejected —
  apps stay independent; each test target defines its own).

## Open Points Resolution

All NEEDS CLARIFICATION items in Technical Context are resolved by R1–R12 (languages,
dependencies, storage, testing, platform, type, performance, constraints, scale). Judgement
calls the problem statement does not settle are recorded in `/questions.md` (Q1–Q6) and
relied on above at R5 (Q1), R7 (Q2, Q6), R6 (Q3), R10 (Q4), R11/R12 and R9 (Q5). None
blocks Phase 1.
