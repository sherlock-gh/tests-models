---
description: "Task list for Cleaning Business Scheduling and Billing"
---

# Tasks: Cleaning Business Scheduling and Billing

**Input**: Design documents from `specs/001-cleaning-scheduling-billing/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md (R1–R12), data-model.md, contracts/ (rules-core.md, desktop-api.md, cleaner-api.md), quickstart.md

**Tests**: Requested. plan.md ("Testing") and quickstart.md §2–§3 mandate contract tests encoding the golden pins G1–G20 of contracts/rules-core.md in BOTH apps: pytest under `desktop/tests/` and XCTest under `CleaningKit/Tests/CleaningKitTests/`. Each contract test is written before the implementation it pins and must be seen to fail first.

**Organization**: Tasks are grouped by user story (US1–US6 from spec.md, priority order P1→P2→P3) so each story can be implemented and tested independently within its app. Rules are duplicated deliberately in Python (`desktop/`) and Swift (`CleaningKit/`) — "the two are not connected" (plan.md Structure Decision); contract tests in each app are the shared source of truth.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Include exact file paths in descriptions

## Path Conventions

- **Twin projects at repository root** (plan.md Project Structure): `desktop/` — Python stdlib web app (back office); `CleaningKit/` — SwiftPM library, no UI (cleaner field logic). All paths below are relative to the repository root.
- Python app runs from the repo root: `python -m desktop.server`, `python -m pytest desktop/tests -q`. Swift package from `CleaningKit/`: `swift build --disable-sandbox`, `swift test --disable-sandbox` (research R1: the nested SwiftPM sandbox is denied on this host).
- Data files stay independent (research R8): desktop `desktop/data.json` (override `CLEANING_DATA`), Swift a caller-supplied file URL. Zero shared paths, zero sync code.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bootstrap both apps so rule code and tests have a home.

- [ ] T001 Create the Python package skeleton: `desktop/__init__.py`, `desktop/tests/__init__.py`, `desktop/static/` directory; document the data file convention `desktop/data.json` auto-created on first write, overridable via `CLEANING_DATA` env var (research R8), per plan.md Project Structure.
- [ ] T002 [P] Create the SwiftPM package manifest `CleaningKit/Package.swift` (Swift 6.1 tools version, Foundation-only library target `CleaningKit`, XCTest test target `CleaningKitTests`), per contracts/cleaner-api.md; verify `swift build --disable-sandbox` succeeds from `CleaningKit/`.
- [ ] T003 [P] Create the root `Procfile` with the single line `web: PORT=$PORT CLEANING_DATA="$DATA/data.json" python -m desktop.server` (questions.md Q7 — demo-server convention, packaging only, not a product rule).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, persistence, time grid, and error discipline that BOTH apps need before any user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Implement dataclasses Cleaner, Client, Job, JobPart, Tap, Invoice, InvoiceLine, Payment in `desktop/models.py` per data-model.md, IDs as "positive integers assigned per collection from a stored seq counter"; `cleaners_needed` "1, 2 or 3 (1–3 cleaners per job, FR-002)"; `expected_length_min` "> 0, minutes" (mean ≈ 248 min / SD ≈ 105 min is a data description, not a validation rule); JobPart `start_min` "on the quarter-hour grid (start_min % 15 == 0) and >= 480 (8:00) for booked parts, FR-003" and `end_min` "for booked parts end_min <= 1020 (17:00)"; InvoiceLine `cents = round_half_up(minutes_worked * 4500 / 60)` "at $45/hour (4500 cents/h; research R2)"; Invoice `total_cents` "= sum of line cents (never re-derived from unrounded values)".
- [ ] T005 [P] Implement JSON store in `desktop/store.py`: whole document `{cleaners, clients, jobs, invoices, payments, seq}`; "Every successful operation rewrites the file via temp-file + rename (POSIX atomic replace); reads happen at operation start" (research R8); "on load, an unreadable/invalid JSON file is an error shown to the user; the app refuses to start the operation and changes nothing (back up the file manually). No silent re-initialization, which would destroy data."
- [ ] T006 [P] Implement time utilities in `desktop/timeutil.py`: `zoneinfo`-based local time (business time zone from env, this host `America/Los_Angeles`); quarter-hour grid "the quarter-hour sequence 8:00, 8:15, … inside Monday–Friday 8:00–17:00"; overlap test "job B overlaps job A for the same cleaner iff B.start < A.end + 60 min" compared on UTC instants ("adding 60 minutes means adding 3600 real seconds"); boundary pins quoted in the task text of T011 (research R3).
- [ ] T007 [P] Define the internal error type `RuleError(message)` in `desktop/store.py` (a module-level class) implementing the research R9 discipline: "Rule functions are pure over a working copy: validate → mutate copy → persist. Errors are values." No exception escapes a request handler.
- [ ] T008 Implement Swift models in `CleaningKit/Sources/CleaningKit/Models.swift` mirroring `desktop/models.py` as structs (Cleaner, Client, Job, JobPart, Tap, Invoice, InvoiceLine, Payment) with the same rules quoted in T004, per contracts/cleaner-api.md.
- [ ] T009 [P] Implement `CleaningKit/Sources/CleaningKit/Store.swift`: `public final class CleaningStore { public init(fileURL: URL, timeZone: TimeZone) throws }` with "throws CleaningError on an unreadable/corrupt data file (research R8); never crashes"; atomic whole-file rewrite per research R8; `CleaningError(message: String)` throwing type per research R9 ("data on disk is unchanged, and the store stays usable (rules-core I10)").
- [ ] T010 [P] Implement `CleaningKit/Sources/CleaningKit/TimeUtil.swift`: quarter-hour grid, Mon–Fri 8:00–17:00 workday and the 1-hour shadow on `Foundation.Calendar`/`Date` in the injected `timeZone`, matching `desktop/timeutil.py` (research R3).
- [ ] T011 Implement shared seed helper `seed_demo()` in `desktop/store.py` and its Swift twin as an extension in `CleaningKit/Tests/CleaningKitTests/`, per research R12: "12 cleaners with distinct ids/names, several clients, jobs whose lengths hover at ~4.14 h mean / ~1.75 h SD exactly as needed per scenario (e.g. 1 h, 3.5 h, 8 h, 10 h)"; "no randomness in tests (deterministic pins: fixed dates in a known week, e.g. Mon 2026-11-16)"; "all available 8:00–17:00 Mon–Fri" (quote: boundary pins "end 12:00 → next start >= 13:00 (12:45 refused); end 12:10 → next start 13:15 (first quarter hour at least an hour later)").

**Checkpoint**: Foundation ready — models, store, time grid, error discipline and seed data exist in both apps; user story work can begin.

---

## Phase 3: User Story 1 — Back office books a job into the earliest safe slot (Priority: P1) 🎯 MVP

**Goal**: Back office creates clients/cleaners and books jobs; the system self-assigns cleaners into the earliest quarter-hour slot on or after the requested day inside 8:00–17:00 Mon–Fri, splits >8 h jobs across consecutive workdays with the same crew, and refuses when no slot exists within 90 days.

**Independent Test**: "With cleaners and clients on file, book jobs (short jobs, a job requested for a Saturday, an 8-hour job, a 10-hour job, and an over-full calendar) and verify placement, self-assignment, part splitting, and refusal — without any other story built." (spec.md US1)

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Contract tests in `desktop/tests/test_booking.py` pinning rules-core goldens: G1 "Cleaner's job ends 12:00; book same cleaner again — next start 13:00 ok; 12:45 rejected"; G2 "Job ends 12:10 — earliest next start 13:15"; G3 "Job requested Saturday — starts Monday 8:00"; G4 "8 h job — one part 8:00–16:00 (same day)"; G5 "10 h job — part 1 = 8 h workday N, part 2 = 2 h workday N+1, same crew"; G6 "Calendar full for 90+ days — refused with message; data file unchanged"; refusal message verbatim "No slot for this job within 90 days of the requested day." (I5).
- [ ] T013 [P] [US1] Contract tests in `CleaningKit/Tests/CleaningKitTests/BookingTests.swift` pinning the same goldens G1–G6 through the public API of contracts/cleaner-api.md (`bookJob(_:)`, `job(id:)`), each test using its own temp store file.

### Implementation for User Story 1

- [ ] T014 [US1] Implement the booking engine in `desktop/booking.py`: per research R4 walk days "D, D+1, … up to and including D+90", the quarter-hour grid per day, "find n cleaners free for every part of a split job. 'Free' = the candidate part (start, end) respects the 1-hour shadow against each of that cleaner's non-cancelled booked parts"; "assign the first n free cleaners in stable id order"; on exhaustion refuse with the message "No slot for this job within 90 days of the requested day." and change nothing — "The scan is run against a working copy of the store and committed only on success (FR-016: nothing changes on refusal)." Uses `desktop/timeutil.py` (T006) and `desktop/models.py` (T004).
- [ ] T015 [US1] Implement the >8 h split in `desktop/booking.py`: per research R5 "floor(L/8h) parts of 8 h plus one final part of the remainder (L mod 8h, when non-zero), on consecutive workdays …, the same n cleaners on every part. Every part starts at 8:00 on its workday (8:00–16:00 for an 8 h part; 8:00–8:00+rest for the final part)" (Q1); "If the chosen crew is not all free for one part's block … the whole split candidate fails and the search moves on — the job moves as a unit." Extends T014.
- [ ] T016 [US1] Add cleaner/client CRUD and booking endpoints to the WSGI app `desktop/app.py` per contracts/desktop-api.md: `GET/POST /api/cleaners`, `GET/PUT/DELETE /api/cleaners/{id}`, "same six for /api/clients", `GET/POST /api/jobs`, `GET /api/jobs/{id}`; POST /api/jobs body `{"client_id", "cleaners_needed": 1..3, "expected_length_min": >0, "requested_day": "YYYY-MM-DD"}` → `201 Job` with system-assigned `cleaner_ids` and `parts`; errors "400 bad fields; 404 unknown client; 400 'No slot ... 90 days ...' message (I5) with store unchanged"; unknown ids on reads → 404 with `{"error": ...}`. Blank-name rule quoted: "required, non-empty after trim" (data-model.md). Routing only — T017 adds the server, US4 adds update/delete of jobs and the deletion side effects.
- [ ] T017 [P] [US1] Implement the HTTP server entry `desktop/server.py`: "wsgiref.simple_server on 127.0.0.1:$PORT (default 18080 in the demo)" (research R11) serving `desktop/static/index.html` at `/` and the `/api/...` routes of `desktop/app.py`; runnable as `python -m desktop.server`.
- [ ] T018 [P] [US1] Implement the Swift booking engine in `CleaningKit/Sources/CleaningKit/Booking.swift`: `bookJob(_ req: BookingRequest)` — "earliest quarter-hour slot >= requested day where cleanersNeeded cleaners are free, 90-day search, >8 h split parts same crew; exhaustion throws 'No slot for this job within 90 days of the requested day.' with nothing written (I5)"; `job(id:)` "unknown -> throw"; same R4/R5 algorithm as T014/T015 using `TimeUtil.swift` (T010) and `Store.swift` (T009).
- [ ] T019 [US1] Implement `desktop/static/index.html`: vanilla HTML+JS single page with "forms for cleaner/client CRUD, a booking form" per research R11 (booking form: client picker, cleaners_needed 1–3, expected length, requested day) plus "a job list with delete buttons"; "Fetch responses with {'error'} render into a page-level error banner."

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently — `python -m pytest desktop/tests/test_booking.py -q` and `swift test --disable-sandbox --filter BookingTests` go green, and the desktop page books jobs end to end.

---

## Phase 4: User Story 2 — Cleaners tap Arrive and Depart in the field, and the invoice issues itself (Priority: P1)

**Goal**: A cleaner sees their day, taps Arrive/Depart recorded to the minute; when the last cleaner departs the invoice issues instantly at $45/h per cleaner line, half-up cent rounding, total = sum of lines.

**Independent Test**: "Given a booked job with assigned cleaners, tap Arrive/Depart for each cleaner (e.g. a cleaner who works 3 hours 30 minutes) and verify recorded minutes, line amounts (3 h 30 min → $157.50), half-up cent rounding, invoice timing at the last departure, and the total." (spec.md US2)

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US2] Contract tests in `desktop/tests/test_taps_billing.py` pinning goldens: G7 "Arrive 9:00, Depart 12:30 — line 15750¢ ($157.50)"; G8 "Two cleaners 210 min + 240 min — lines 15750¢ + 18000¢; total 33750¢"; G11 "Cleaner with arrivals arrives again — refused, nothing changes"; G12 "Depart with no Arrive — refused, nothing changes"; I7 "invoice exists iff every assigned cleaner has departed; issued in that same operation"; line cents "round-half-up(minutes × 4500 ÷ 60)"; taps "recorded to the minute (seconds truncated; FR-008)".
- [ ] T021 [P] [US2] Contract tests in `CleaningKit/Tests/CleaningKitTests/TapAndInvoiceTests.swift` pinning G7/G8/G11/G12 through `jobsForToday(cleanerId:on:)`, `arrive(jobId:cleanerId:atInstant:)`, `depart(jobId:cleanerId:atInstant:)`; "the integer (minutes * 4500 + 30) / 60 form is pinned by a test so both apps agree to the cent" (research R2).

### Implementation for User Story 2

- [ ] T022 [US2] Implement billing in `desktop/billing.py` per research R2: money in "integer cents. Rate = 4500 cents/hour = exactly 75 cents/minute"; line = "round_half_up(minutes × 4500 ÷ 60), computed as Fraction(minutes*4500, 60) in Python (or Decimal quantized with ROUND_HALF_UP), never as a binary float"; invoice issued at last departure carrying `lines` (one per cleaner: `cleaner_id`, `minutes_worked`, `cents`) and `total_cents` "= sum of line cents"; goldens "3 h 30 min = 210 min → 15750 cents ($157.50); 4 h → 18000 cents ($180.00); the same two cleaners on one invoice → 33750 cents ($337.50)".
- [ ] T023 [US2] Implement day list + taps in `desktop/booking.py` (tap section) and wire endpoints in `desktop/app.py` per contracts/desktop-api.md: `GET /api/jobs/today?date=YYYY-MM-DD&cleaner_id=N` → jobs "assigned to that cleaner starting that day (US2 AC1)" showing "client, start time, expected length"; `POST /api/jobs/{id}/arrive` ("tap recorded to the minute; first arrival ⇒ in_progress", "400 second Arrive / wrong cleaner / future part not started"); `POST /api/jobs/{id}/depart` ("400 Depart without Arrive"; invoice issued "when last cleaner departs" with `invoice.issued_at` now). Tap rules quoted: "Arrive requires status booked/in_progress and the job's (first) part started (not in the future for this cleaner); a second Arrive before Depart is refused; Depart without a prior Arrive is refused" (data-model.md).
- [ ] T024 [US2] Implement `CleaningKit/Sources/CleaningKit/Billing.swift` per research R2: Swift line cents "(minutes * 4500 + 30) / 60" integer arithmetic; "Decimal.rounded() defaults must not be trusted here"; invoice total = "sum of the rounded line values"; payment compares "cents for exact equality (FR-014)" — settlement behavior itself is T034. Depends on T008/T009.
- [ ] T025 [US2] Implement `CleaningKit/Sources/CleaningKit/DayOps.swift`: `jobsForToday(cleanerId:on:)`, `arrive(jobId:cleanerId:atInstant:)`, `depart(jobId:cleanerId:atInstant:)` per contracts/cleaner-api.md — "Last cleaner's Depart issues the invoice in the same write and the returned job carries invoice (I7)"; all writes go through `Store.swift` atomic rewrite. Depends on T024.

**Checkpoint**: At this point, User Stories 1 AND 2 work independently — taps to the minute, invoice timing and amounts 15750/18000/33750¢ pinned by green tests in both apps.

---

## Phase 5: User Story 3 — Cleaners ask for more time without wrecking the rest of the day (Priority: P2)

**Goal**: Arrived cleaners extend in uncapped 20-minute steps; later jobs left inside the 1-hour shadow are rebooked by the booking rule from newEnd + 1 h, cascading, all-or-nothing.

**Independent Test**: "Given a cleaner who has arrived on a job with a later booked job, take 20-minute extensions until the later job falls inside the 1-hour shadow, and verify the later job is rebooked by the booking rule from at least 1 hour after the new end, cascading where needed, leaving no overlap or double booking." (spec.md US3)

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T026 [P] [US3] Contract tests in `desktop/tests/test_extensions.py` pinning goldens: G13 "More-time before Arrive / after completion — refused, nothing changes"; G14 "Extension leaves later job < 1 h after new end — that job rebooked ≥ new end + 1 h by booking rule; cascade until clean"; plus US3 AC4 "extensions that push an end past 17:00 are legal" and the all-or-nothing rule: "if any step cannot place a job within its 90-day window, the entire extension is refused with a message and nothing changes" (research R6).
- [ ] T027 [P] [US3] Contract tests in `CleaningKit/Tests/CleaningKitTests/ExtensionTests.swift` pinning G13/G14 through `requestMoreTime(jobId:cleanerId:)` returning `MoreTimeOutcome { job, rebooked }`.

### Implementation for User Story 3

- [ ] T028 [US3] Implement extensions + cascade in `desktop/booking.py` (extension section) per research R6: valid only when "that cleaner has tapped Arrive on the job and has not departed (else refused with an error, nothing changes)"; "each call adds 20 minutes to that cleaner's job end"; "No cap; it may pass 17:00 (Q3)"; after the extension "examine the cleaner's future jobs (nobody tapped Arrive) whose start falls < 60 min after the new end; rebook each such job by the booking rule with the earliest slot starting no earlier than newEnd + 60 min"; "Rebooking a job can push it into another future job's shadow → cascade, repeating until no overlap exists. Already-arrived jobs are never moved"; the whole cascade runs "on a working copy and commits atomically" or is refused with "a message and nothing changes." Wire `POST /api/jobs/{id}/more-time` in `desktop/app.py` returning "`20 min` extension applied, Job + any `rebooked:[{job_id, parts}]` (I14/G14)" and "400 not-arrived/finished".
- [ ] T029 [US3] Implement `CleaningKit/Sources/CleaningKit/Extension.swift` (added to the `CleaningStore` surface in `CleaningKit/Sources/CleaningKit/DayOps.swift` as a `requestMoreTime` extension): "20-minute step; only a cleaner who arrived and not departed (else throw); no cap, past 17:00 allowed. Later < 1 h-shadow jobs rebooked by booking rule with floor at new end + 1 h, cascading; all-or-nothing (I1, G14)" (contracts/cleaner-api.md). Also append the `MoreTimeOutcome`/`RebookedJob` structs to `CleaningKit/Sources/CleaningKit/Models.swift`. Depends on T018/T025.

**Checkpoint**: At this point, US3 is independently verifiable — green extension tests show cascades never leave an overlap (I1) and an extension whose cascade fails changes nothing.

---

## Phase 6: User Story 4 — Records maintenance with safe deletions (Priority: P2)

**Goal**: Full CRUD on cleaners/clients/jobs in both apps; cleaner deletion rebooks their future jobs, client deletion cancels their future jobs, invoiced jobs are undeletable, issued invoices are immutable.

**Independent Test**: "Exercise every create, read, update and delete on cleaners, clients and jobs, including deleting a cleaner with future and started jobs, deleting a client with future jobs, and attempting to delete an invoiced job or alter an issued invoice." (spec.md US4)

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 [P] [US4] Contract tests in `desktop/tests/test_records.py` pinning goldens: G15 "Delete cleaner with 2 future + 1 arrived job — 2 future rebooked with free cleaners; arrived job untouched"; G16 "Delete client with future jobs — those jobs cancelled"; G17 "Delete job with issued invoice — refused; job and invoice unchanged"; G20 "Update/delete issued invoice; pay settled invoice — refused, nothing changes"; plus edge cases "Deleting a cleaner with no future jobs, or a client with no future jobs: the record is removed with nothing to rebook or cancel" and PUT-job: a "booked, not-yet-deleted" job update "is cancelled and rebooked by the booking rule" (desktop-api.md).
- [ ] T031 [P] [US4] Contract tests in `CleaningKit/Tests/CleaningKitTests/RecordsTests.swift` pinning G15/G16/G17/G20 through `deleteCleaner(id:)` ("future jobs rebooked (I9)"), `deleteClient(id:)` ("future jobs cancelled"), `deleteJob(id:)` ("issued-invoice job -> throw 'invoice has been issued'") and `updateInvoice/deleteInvoice` ("always throw (I9)").

### Implementation for User Story 4

- [ ] T032 [US4] Implement deletions/rebooking in `desktop/booking.py` (records section) and finish CRUD endpoints in `desktop/app.py` and `desktop/store.py` per research R7: Delete cleaner — "remove the cleaner; every future job they are on is rebooked by the booking rule (R4) with any free cleaners … and a multi-part job's future parts rebook as a unit (Q2)"; "the deleted cleaner is removed from the crew of in-progress jobs, which then complete and invoice on the remaining cleaners' departures, listing only remaining cleaners' lines; already-issued invoices survive untouched" (Q6). Delete client — "remove the client and cancel all their future jobs (cancel = status cancelled, jobs stay visible, no rebooking, they leave every cleaner's schedule and shadow book)". Delete job — "allowed while not invoiced; refused with a message once its invoice has been issued (FR-012)"; `PUT /api/jobs/{id}` with `{expected_length_min?, requested_day?}` on a booked job "⇒ it is cancelled and rebooked by the booking rule", "400 if invoice issued / arrived-on". Future-job definition quoted: "nobody has tapped Arrive on" (FR-011), evaluated at deletion time.
- [ ] T033 [US4] Implement record mutations in `CleaningKit/Sources/CleaningKit/DayOps.swift` (records extensions): `updateCleaner(id:name:)` ("unknown id -> throw"), `deleteCleaner(id:)` ("future jobs rebooked (I9)"), `updateClient(id:name:)`, `deleteClient(id:)` ("future jobs cancelled"), `deleteJob(id:)` ("issued-invoice job -> throw 'invoice has been issued'") per contracts/cleaner-api.md, reusing `Booking.swift` for rebooking. Depends on T018.

**Checkpoint**: At this point, US4 is independently verifiable — every CRUD verb works and the deletion rules (rebook vs cancel vs refuse) hold without moving arrived-on jobs.

---

## Phase 7: User Story 5 — Back office settles invoices (Priority: P2)

**Goal**: Settled/unsettled visibility; exactly one payment of the exact total settles an invoice; every other amount is refused.

**Independent Test**: "Produce issued invoices, record one full payment and non-full payments, and verify settled/unsettled grouping and refusal of every other amount." (spec.md US5)

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T034 [P] [US5] Contract tests in `desktop/tests/test_settlement.py` pinning goldens: G18 "Pay unsettled invoice with total±1¢ — refused, remains unsettled"; G19 "Pay exact total — settled"; G20's pay-a-settled-invoice half; I8 "exactly one payment, cents-equal to the total, sets settled; any other amount (or a second payment, or unknown invoice) is refused, invoice stays as it was"; edge case "Payment on an already-settled invoice, a second payment on a settled invoice, or payment for an invoice that doesn't exist: refused, nothing changes."
- [ ] T035 [P] [US5] Contract tests in `CleaningKit/Tests/CleaningKitTests/SettlementTests.swift` pinning G18/G19/G20 through `pay(invoiceId:amountCents:)` ("exact full amount only; anything else throws; settled invoice -> throw (I8)") and `invoices()` / `invoice(id:)`.

### Implementation for User Story 5

- [ ] T036 [US5] Implement settlement in `desktop/billing.py` and endpoints in `desktop/app.py` per FR-014 and contracts/desktop-api.md: `GET /api/invoices` ("each with 'settled': bool"), `GET /api/invoices/{id}` (404 unknown), `POST /api/invoices/{id}/pay` body `{"amount_cents": int}` → "Invoice now settled:true when amount_cents == total_cents", "400 other amount / already settled / 404"; "PUT/DELETE /api/invoices* | any | — | 400 always (issued invoices never change/delete)" — immutability rule quoted: "Issued invoices never change and are never deleted" (FR-012). Payment rules quoted from data-model.md: "amount_cents > 0"; "Creation succeeds only when the invoice is unsettled and amount_cents == invoice.total_cents — 'paid in full in one payment'". Settled state derives from the accepted payment record's existence.
- [ ] T037 [US5] Implement settlement in `CleaningKit/Sources/CleaningKit/Billing.swift` endpoint surface (extend `CleaningKit/Sources/CleaningKit/Billing.swift`): `invoices()`, `invoice(id:)` ("unknown -> throw"), `pay(invoiceId:amountCents:)` ("exact full amount only; anything else throws; settled invoice -> throw (I8)"), `updateInvoice(id:...)/deleteInvoice(id:)` "always throw (I9)" per contracts/cleaner-api.md. Depends on T024.

**Checkpoint**: At this point, US5 is independently verifiable — settled/unsettled grouping correct, and only an exact single full-total payment ever changes an invoice's state.

---

## Phase 8: User Story 6 — Cleaner utilization reporting (Priority: P3)

**Goal**: Per-cleaner billable hours out of 8 per workday and 40 per Mon–Sun week, midnight-spanning work split across days, values uncapped.

**Independent Test**: "Supply known worked time (e.g. a cleaner who works 22:00 to 2:00) and verify per-day and per-week totals, including midnight-spanning splits and totals above 8/40." (spec.md US6)

### Tests for User Story 6 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T038 [P] [US6] Contract tests in `desktop/tests/test_utilization.py` pinning goldens: G9 "Worked 22:00–2:00 — utilization: 2 h day 1, 2 h day 2"; G10 "45 h in a Mon–Sun week — weekly report shows 45 of 40 (no cap)"; US6 AC1 "3 hours 30 minutes on Monday → 3.5 of 8 hours"; US6 AC4 "a cleaner with no worked time in a period … show 0 hours, not an error"; rule quotes: "billable hours worked out of 8 per workday, and out of 40 per week (Monday to Sunday). Work that runs past midnight counts on each day for the part worked that day. Hours may exceed 8 or 40." (FR-015)
- [ ] T039 [P] [US6] Contract tests in `CleaningKit/Tests/CleaningKitTests/UtilizationTests.swift` pinning G9/G10 and the 0-hour empty case through `dailyUtilization(date:)` / `weeklyUtilization(weekOf:)` returning `UtilizationEntry {cleanerId, name, hoursWorked, hoursOf}` — "cleaner with no taps -> hoursWorked 0.0, never an error (US6 AC4)".

### Implementation for User Story 6

- [ ] T040 [US6] Implement utilization in `desktop/utilization.py` per research R10: "Billable minutes for a cleaner day D = sum over their tap pairs (Arrive→Depart) of the minutes that fall within calendar day D in local time; a tap span crossing midnight splits at 00:00 local and contributes to both days (22:00→02:00 → 120 min each day)"; "Only tapped time counts (spec Assumption); booked-but-no-show time never does. Weekend tap minutes still count on their day and in the Mon–Sun week total (Q4)"; expose `GET /api/utilization/daily?date=YYYY-MM-DD` → `{"entries":[{"cleaner_id","cleaner_name","hours_worked","hours_of":8}]}` and `GET /api/utilization/weekly?week_start=YYYY-MM-DD` (a Monday) → same shape "with hours_of: 40; values may exceed (G10)" in `desktop/app.py`; "Bad dates / unknown cleaner → 400/404 with message, nothing stored changes."
- [ ] T041 [US6] Implement `CleaningKit/Sources/CleaningKit/Utilization.swift`: `dailyUtilization(date:)` / `weeklyUtilization(weekOf:)` with `UtilizationEntry {cleanerId, name, hoursWorked: Double /* minutes/60; midnight-split attribution (G9) */, hoursOf: Int /* 8 daily, 40 weekly; hoursWorked may exceed (G10) */}` per contracts/cleaner-api.md, matching T040. Depends on T010/T009.
- [ ] T042 [US6] Extend `desktop/static/index.html` with the remaining page sections per research R11: "day/week utilization, invoice list with settled/unsettled grouping and a pay box" (the CRUD/booking forms from T019 and the job list stay as built); error banner behavior unchanged.

**Checkpoint**: All user stories are now independently functional; every G1–G20 golden has a pinned test in both apps.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature validation across both apps.

- [ ] T043 [P] Cross-app parity test: in a new file `desktop/tests/test_rules_core_parity.py`, systematically assert the shared invariants once more — "after any successful operation a full-store scan finds zero violations" (I1) after booking, extension and rebooking flows; refusal message bytes "No slot for this job within 90 days of the requested day."; and the full G1–G20 table of contracts/rules-core.md re-run against `desktop/`.
- [ ] T044 Run the error-discipline spot checks of `specs/001-cleaning-scheduling-billing/quickstart.md` §4 against the running desktop app ("cleaners_needed = 5", "job 99999", "pay a settled invoice"), verifying each response `{"error": ...}` with the data file byte-identical afterwards and the server still answering (I10); record results in quickstart.md as checked.
- [ ] T045 [P] Verify the Swift suite end to end: from `CleaningKit/`, `swift build --disable-sandbox` then `swift test --disable-sandbox` all green (BookingTests, TapAndInvoiceTests, ExtensionTests, RecordsTests, SettlementTests, UtilizationTests), "each test using its own temp store file (the two apps' files never touch, research R8)".
- [ ] T046 Run the full desktop suite from the repo root: `python -m pytest desktop/tests -q` all green (test_booking, test_taps_billing, test_extensions, test_records, test_settlement, test_utilization, test_rules_core_parity) per quickstart.md §3.
- [ ] T047 Walk `specs/001-cleaning-scheduling-billing/quickstart.md` §1 through the live desktop page (12 cleaners, booking walkthrough, more-time overnight span, settlement, refusals, utilization) confirming the page's "Definition of done for this feature": "Every acceptance scenario in spec.md User Stories 1–6 passes in both apps … and neither app crashes or mutates the data file on any error."

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phases 3–8)**: All depend on Foundational completion.
  - US1 (P1) and US2 (P1) are the MVP pair — headline pains; deliver US1 first, then US2.
  - US3 (P2) builds on booking and taps; US4 (P2) builds on booking and the deletion rules; US5 (P2) depends only on issued invoices (US2's output); US6 (P3) needs tapped time (US2) and benefits from US3's overnight extensions.
  - Story test tasks are contract tests pinned to independent fixtures (their own seed/temp files), so a later story's tests can be written even before an earlier story ships — only the implementation must respect the order below.
- **Polish (Phase 9)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependencies on other stories.
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) — books from fixtures, independently testable; its invoice issuance does not require US3–US6.
- **User Story 3 (P2)**: Depends on US1 (booking rule for rebooking) and US2 (Arrive state gates the request) implementations; independently testable given both.
- **User Story 4 (P2)**: Depends on US1 (booking rule for cleaner-deletion rebook) and US2 (arrived status, issued invoice for the refusal paths); independently testable given both.
- **User Story 5 (P2)**: Depends on US2 (an issued invoice to settle) — nothing else; independently testable.
- **User Story 6 (P3)**: Depends on US2 (tapped minutes); independently testable with directly supplied tap data.

### Within Each Story

- Tests MUST be written and FAIL before implementation (T012/T013 before T014–T019, etc.).
- Models before services; services (booking/billing) before endpoints (app.py routes, Swift public methods); endpoints before page UI.
- Same-file tasks run sequentially in ID order (e.g. T014 → T015 in `desktop/booking.py`; T016/T023/T028/T032/T036 in `desktop/app.py`; T022/T024/T037 in the billing files; T032/T033/T025/T029 records/day-ops files).
- Story complete (tests green) before moving to the next priority.

### Parallel Opportunities

- All Setup tasks marked [P] (T002/T003 with T001) can run in parallel.
- Foundational: with T004/T008 done, T005/T006/T007 parallelize (Python side) and T009/T010 (Swift side); T011 needs the stores in place.
- Once Foundational completes, US1 and US2 (and the test-writing for every story) can proceed in parallel by different team members.
- All tests for a story marked [P] (the desktop test file vs the Swift test file) run in parallel — different files, different languages.
- Same-file rule: Python-side and Swift-side tasks for the same story never block each other (fully independent apps).

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (write first, ensure they fail):
Task: "Contract tests in desktop/tests/test_booking.py pinning goldens G1-G6"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/BookingTests.swift pinning the same goldens G1-G6"

# Once tests fail for the right reason, launch Python and Swift implementations together:
Task: "Implement the booking engine in desktop/booking.py (T014)"
Task: "Implement the Swift booking engine in CleaningKit/Sources/CleaningKit/Booking.swift (T018)"

# Then UI and server in parallel:
Task: "Implement the HTTP server entry desktop/server.py (T017)"
Task: "Implement desktop/static/index.html booking forms (T019)"
```

## Parallel Example: User Story 2

```bash
Task: "Contract tests in desktop/tests/test_taps_billing.py pinning G7/G8/G11/G12"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/TapAndInvoiceTests.swift pinning G7/G8/G11/G12"

Task: "Implement billing in desktop/billing.py (T022)"
Task: "Implement CleaningKit/Sources/CleaningKit/Billing.swift (T024)"
```

## Parallel Example: User Story 3

```bash
Task: "Contract tests in desktop/tests/test_extensions.py pinning G13/G14"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/ExtensionTests.swift pinning G13/G14"

Task: "Implement extensions + cascade in desktop/booking.py (T028)"
Task: "Implement CleaningKit/Sources/CleaningKit/Extension.swift (T029)"
```

## Parallel Example: User Story 4

```bash
Task: "Contract tests in desktop/tests/test_records.py pinning G15/G16/G17/G20"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/RecordsTests.swift pinning G15/G16/G17/G20"

Task: "Implement deletions/rebooking in desktop/booking.py + desktop/app.py (T032)"
Task: "Implement record mutations in CleaningKit/Sources/CleaningKit/DayOps.swift (T033)"
```

## Parallel Example: User Story 5

```bash
Task: "Contract tests in desktop/tests/test_settlement.py pinning G18/G19/G20"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/SettlementTests.swift pinning G18/G19/G20"

Task: "Implement settlement in desktop/billing.py + desktop/app.py (T036)"
Task: "Implement settlement in CleaningKit/Sources/CleaningKit/Billing.swift (T037)"
```

## Parallel Example: User Story 6

```bash
Task: "Contract tests in desktop/tests/test_utilization.py pinning G9/G10"
Task: "Contract tests in CleaningKit/Tests/CleaningKitTests/UtilizationTests.swift pinning G9/G10"

Task: "Implement utilization in desktop/utilization.py + endpoints (T040)"
Task: "Implement CleaningKit/Sources/CleaningKit/Utilization.swift (T041)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003).
2. Complete Phase 2: Foundational (T004–T011) — CRITICAL, blocks all stories.
3. Complete Phase 3: User Story 1 (T012–T019): write G1–G6 tests first, watch them fail, then implement.
4. **STOP and VALIDATE**: `python -m pytest desktop/tests/test_booking.py -q` green; serve the page and book a Saturday job (→ Monday 8:00), an 8 h job (→ 8:00–16:00), a 10 h job (→ 8 h + 2 h same crew), and an over-full calendar (→ refused, unchanged).
5. Deploy/demo if ready (Procfile T003 already in place).

### Incremental Delivery

1. Setup + Foundational → foundation ready in both apps.
2. US1 → booking without overlaps/double-bookings (core pain #1) → demo (MVP!).
3. US2 → taps to the minute + instant accurate invoices ($157.50 golden) (core pain #2) → demo.
4. US3 → safe more-time cascades → demo.
5. US4 → full CRUD with rebook/cancel/refuse semantics → demo.
6. US5 → settlement view, full-total-only payments → demo.
7. US6 → utilization out of 8/40 with midnight splits → demo.
8. Polish (T043–T047) → both suites green + quickstart walked → feature done.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (Python half and Swift half split naturally).
2. Once Foundational is done:
   - Developer A: US1 then US3 (booking/cascade in `desktop/booking.py` + `Booking.swift`)
   - Developer B: US2 then US5 (taps/invoices/settlement in `billing.py` + `Billing.swift` + `DayOps.swift`)
   - Developer C: US4 then US6 (records + utilization)
3. Stories complete and integrate independently — each developer's tests pin the same rules-core goldens.

---

## Notes

- [P] tasks = different files, no dependencies; tasks sharing a file (e.g. `desktop/booking.py` across T014/T015/T023/T028/T032, `desktop/app.py` across T016/T023/T028/T032/T036/T040) run sequentially in ID order despite touching one file.
- [Story] label maps task to specific user story for traceability; test tasks carry their story label too.
- Each user story is independently completable and testable: story tests seed their own fixtures (T011, research R12) and Swift tests each use their own temp store file.
- Verify tests fail before implementing — every "Tests for User Story N" block first.
- Commit after each task or logical group (checkpoint-level commits minimum).
- Constraints quoted verbatim above: 4500 cents/h money rule and half-up line rounding, golden cents 15750/18000/33750, quarter-hour grid and >= 480/<= 1020 part bounds, 1-hour shadow with 12:00→13:00-not-12:45 and 12:10→13:15, floor(L/480)×480 + remainder split with same crew, 90-day search with the verbatim refusal message, 20-minute uncapped extensions, taps "to the minute", one-payment exact-total settlement, and out-of-8/out-of-40 uncapped utilization with midnight splitting.
- Avoid: vague tasks, same-file conflicts (see the file-sharing note), cross-story dependencies that break independence (US2 tests never call US3–US6 code paths; only the listed implementation prereqs bind stories).
- The two data files must remain independent: no shared paths, no sync code (research R8); any "cross-referencing" between apps is a defect.
