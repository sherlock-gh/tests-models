---
description: "Task list for Cleaning Scheduling and Billing implementation"
---

# Tasks: Cleaning Scheduling and Billing

**Input**: Design documents from `specs/001-cleaning-scheduling-billing/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are mandated by the plan's Technical Context ("Testing: pytest (Python side), XCTest (Swift side), plus a scripted audit workload exercising SC-001…SC-007") and by the contracts' parity gate. Contract/parity tests are written before the implementations they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Note two exceptions forced by the design: US5 (utilization) depends on worked times from US2, and US4 (extensions/removals) rebooks jobs created via US1 and must not mutate invoices from US3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

## Path Conventions

Dual project per plan.md: `webapp/` (Python back office), `CleanerApp/` (logic-only Swift package), `shared/` (rule statement), `tests/` (pytest at repo root). Swift tests live inside `CleanerApp/Tests/` per SwiftPM convention.

<!--
  Rule sources for every task below: shared/rule-spec.md (canonical), research.md
  D-1..D-9 (decisions), data-model.md (fields/constraints), contracts/ (routes/API).
  Quoted constraint text is from data-model.md / spec.md verbatim.
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold both packages and the shared rule statement so neither side can drift from a missing baseline.

- [ ] T001 Author the canonical language-neutral rule statement in shared/rule-spec.md covering: workday window "8:00–17:00, Monday–Friday"; refusal when "expected_length_min ... > 540 (9 h)" (FR-002); symmetric spacing: "no two `scheduled` jobs J1 (earlier) and J2 with J2.start < J1.end + 60 min, symmetrically. Jobs exactly 60 min apart are legal"; "Candidate days = workdays (Mon–Fri) on or after the requested day, up to a 52-workday horizon ... First candidate with ≥ required distinct free cleaners wins; assign the lowest-id free cleaners" (D-3); +20-minute extension with no 17:00 cap for the extending job (FR-008/009, D-4); delete-cleaner rebooking / delete-client cancellation with abort-and-restore on infeasibility (D-5); "Line per cleaner = round(worked_hours × 45, 2 cents) (round-half-up on the exact Decimal), total = sum of rounded lines" (D-6); full-payment-only settlement (D-7); utilization against 8 h/day and 40 h/week (D-8); atomic-write, change-nothing-on-error discipline (D-9). Both packages cite this file (research.md D-1).
- [ ] T002 [P] Create the Python package scaffold: webapp/cleaning/__init__.py and webapp/requirements.txt (flask; stdlib wsgiref fallback needs nothing) per plan.md Project Structure and quickstart.md Setup.
- [ ] T003 [P] Create the SwiftPM scaffold: CleanerApp/Package.swift (Swift 5.9+, swift-tools-version, single target CleaningLogic, Foundation only, no third-party packages) with empty dirs CleanerApp/Sources/CleaningLogic/ and CleanerApp/Tests/CleaningLogicTests/ per plan.md.
- [ ] T004 [P] Add repo hygiene files: .gitignore covering webapp/data/, .venv/, CleanerApp/.build/, __pycache__/ per plan.md ("data/ — Local JSON store (gitignored content)").
- [ ] T005 [P] Create the pytest scaffolding at the repo root: tests/unit/__init__.py, tests/contract/__init__.py, tests/audit/__init__.py, and a root conftest.py that puts webapp/ on sys.path so `pytest tests/` runs from the repo root (quickstart.md "Run the tests").

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entities, persistence, canonical rule engine, and server entry point that MUST exist before ANY user story. Mirror rule engine (Swift) is built alongside as both sides' tests are transcribed from the same shared/rule-spec.md scenario table (research.md D-1).

**⚠️ CRITICAL**: No user story work begins until every task in this phase completes.

- [ ] T006 Implement Python records in webapp/cleaning/models.py: Cleaner (id "unique, system-assigned"; name "required, non-empty, trimmed"), Client (same fields), Job ("client_id ... required, must exist (FR-002)", "requested_day ... date, required", "expected_length_min ... required, > 0; > 540 (9 h) refused (FR-002)", "cleaners_required ... required, ∈ {1, 2, 3} (FR-002)", booked_start "on Mon–Fri, ≥ 8:00", booked_end "≤ 17:00 unless pushed by extension (FR-008)", state enum "`scheduled` / `in_progress` / `complete` / `cancelled`", "invoice_id int? set at completion, same write (FR-011)"), JobAssignment ("cleaner_id ... distinct within the job", "arrival datetime? set by Arrive tap; not before booked_start day", "departure datetime? ≥ arrival (same instant allowed → $0.00 line)", "worked_min int? = departure − arrival, derived on Depart (FR-007)"), Invoice ("lines ... amount = round(worked_min/60 × $45, 0.01) half-up", "total Decimal = Σ rounded line amounts", "settled bool false at issue (FR-014)", "payment_amount Decimal? set only on full payment (FR-013)", "payment_date datetime? set only on full payment"), UtilizationReport (derived view: day worked/8 h, week worked/40 h). Money is Decimal in 2-dp cents (never float); IDs are integer sequence numbers per entity type (data-model.md).
- [ ] T007 Implement the canonical rule engine (pure functions) in webapp/cleaning/rules.py per research.md D-3..D-8 and shared/rule-spec.md: earliest-slot scan (workdays on/after requested day, 52-workday horizon; minute-grid candidate starts "from 8:00 ... while start + length ≤ 17:00"; free = no scheduled job violating 60-min spacing "both directions — FR-005 is symmetric spacing"; lowest-id free cleaners win; weekend requested day moves to the following Monday); >540-min refusal before any search ("the 9-hour refusal (> one workday) happens before any search, so nothing changes on refusal"); extension +20 min + cascade ("minimum start = max(its current day, day of extended-end + 60 min) ... repeating until a full pass finds no violation" and abort/restore on infeasibility); delete-cleaner rebooking ("earliest start first ... the deleted cleaner is removed from the candidate pool first") and delete-client cancellation of future `scheduled` jobs only; tap-order validation ("Arrive requires state `scheduled`/`in_progress` with this assignment's arrival unset; Depart requires arrival set, departure unset"); invoice math (round-half-up Decimal line = worked_hours × 45, total = sum of rounded lines); settlement ("amount ≠ total (exact cent/Decimal equality) → refused ... equal → settled"); utilization day/week sums (D-8).
- [ ] T008 Implement the Python JSON store in webapp/cleaning/store.py per research.md D-9: single file `webapp/data/store.json`, load on init, "Atomic write: serialize → write temp in same dir → `os.replace`", "Every operation runs fully in memory on a loaded copy; only a successful, conflict-free operation is persisted", integer sequence counters per entity type, user-facing error results (message strings) instead of crashes.
- [ ] T009 [P] Implement Swift structs in CleanerApp/Sources/CleaningLogic/Models.swift: `Cleaner`, `Client`, `Job`, `JobAssignment`, `Invoice`, `InvoiceLine`, `UtilizationReport` mirroring data-model.md "field-for-field; money is `Decimal`, times `Date` at minute granularity", plus `public enum CleaningError: Error, Equatable` with exactly the cases listed in contracts/cleaner-logic-swift.md (notFound, invalidInput, jobTooLong, noFeasibleSlot, tapOutOfOrder, wrongCleaner, paymentAmountMismatch, alreadySettled, notEnoughCleaners).
- [ ] T010 [P] Implement the mirrored Swift rule engine in CleanerApp/Sources/CleaningLogic/Rules.swift — "Mirror of rules.py (same rule statement)" (plan.md) — porting every pure rule from T007 verbatim from shared/rule-spec.md (same horizon, same tie-breaks, same half-up rounding via Decimal).
- [ ] T011 [P] Implement the Swift local JSON store in CleanerApp/Sources/CleaningLogic/Store.swift: `public init(fileURL: URL)` loading the package's own file, `save()` with atomic write, per research.md D-9. The full public Store API surface (addCleaner/jobs/arrive/depart/extend/invoice/recordPayment/utilizationReports) is completed in the story phases below; each mutating op is declared and implemented all-or-nothing (FR-016, contracts/cleaner-logic-swift.md).
- [ ] T012 [P] Implement the server entry point in webapp/app.py: Flask app (stdlib `wsgiref.simple_server` fallback per D-2), serving on 127.0.0.1 at $PORT (ports 18080–18089 during validation, per plan.md Target Platform).
- [ ] T013 Transcribe the shared scenario table into a pytest-runnable scenario module in tests/unit/scenarios.py covering "US1–US5 acceptance scenarios + all Edge Cases" (contracts/cleaner-logic-swift.md Parity gate) as pure rule-level cases with expected outputs/errors, and the mirrored replay skeleton in CleanerApp/Tests/CleaningLogicTests/ParityScenariosTests.swift (XCTest) against the same table.

**Checkpoint**: Both packages build/import; rule engine, store, and scenario table exist. User stories can now begin.

---

## Phase 3: User Story 1 - Back office books jobs without conflicts (Priority: P1) 🎯 MVP

**Goal**: CRUD for cleaners/clients/jobs plus conflict-free earliest-slot booking ("The system assigns the cleaners on its own and books the job into the earliest slot, on or after the requested day, where enough cleaners are free").

**Independent Test**: "Create cleaners and clients, book a series of jobs under varying demand, then verify no cleaner holds two jobs where the second starts less than 1 hour after the first ends, every scheduled job sits inside 8:00–17:00 Monday–Friday, and each job landed in the earliest feasible slot." (spec.md US1)

### Tests for User Story 1 (write first, must fail before implementation)

- [ ] T014 [P] [US1] Contract tests for cleaner/client pages in tests/contract/test_cleaner_client_pages.py: GET/POST `/cleaners` and `/clients` (list/create name), GET/POST `/cleaners/<id>` (view/update name), POST `/cleaners/<id>/delete`, same shape for clients — "POST→redirect on success; error banner + no change on bad input (FR-001, FR-016)", "no route emits 5xx for domain refusals" (contracts/backoffice-web.md).
- [ ] T015 [P] [US1] Contract tests for booking and job CRUD in tests/contract/test_booking_pages.py: POST `/jobs/book` with "client_id, cleaners_required ∈ {1,2,3}, hours (>0, ≤9), requested_day"(date input) incl. US1-AC1 (3-cleaner 4 h next Monday → earliest workday, earliest start), US1-AC2 (free cleaner chosen, gap ≥ 1 h), US1-AC3 (9.5 h refused, "store byte-identical" — V3), weekend → following Monday ≥ 8:00 (V14), no-feasible-slot refusal with "nothing changes and no waiting queue is created"; GET `/jobs`, `/jobs/<id>`, `/jobs/<id>/edit`, POST `/jobs/<id>` (edit "client, length, required count → rebooks") and `/jobs/<id>/delete` (contracts/backoffice-web.md).
- [ ] T016 [P] [US1] Unit tests for the booking rule in tests/unit/test_rules_booking.py encoding US1-AC1..AC4 and edge cases (weekend, >540 min refusal before search, symmetric 60-min spacing incl. exactly-60-min-apart legal, lowest-id tie-break, fewer-distinct-cleaners-than-required → refused "noFeasibleSlot"), driving webapp/cleaning/rules.py directly.
- [ ] T017 [P] [US1] Swift XCTest suite for booking in CleanerApp/Tests/CleaningLogicTests/BookingTests.swift replaying the same US1 scenarios through the public `bookJob(clientID:cleanersRequired:expectedLength:requestedDay:)` API, expecting `throws .jobTooLong` / `.noFeasibleSlot` / `.notFound` per contracts/cleaner-logic-swift.md.

### Implementation for User Story 1

- [ ] T018 [US1] Implement the HTML templates for the back office in webapp/templates/: dashboard (`/` "links to all lists"), cleaner/client list+detail+delete forms, job list/detail/edit and the booking form (client select, cleaners_required 1|2|3, hours, requested_day date input), each rendering a visible error-message banner per contracts/backoffice-web.md Error contract ("Every failure returns an HTTP 200 page (redirect-back) carrying a visible error message naming what went wrong").
- [ ] T019 [US1] Implement the CRUD + booking route handlers in webapp/cleaning/views.py (wired in webapp/app.py): create/read/update/delete cleaners and clients (name trimmed, "missing record, bad input" → error banner, no change), book job via rules.py earliest-slot scan (FR-003/FR-004/FR-005), job edit rebooks through the booking rule (client, length, required count), job delete removes; every op persisted via store.py only on success (FR-016). Depends on T006–T008, T018.
- [ ] T020 [US1] Implement the Swift Store record + booking API in CleanerApp/Sources/CleaningLogic/Store.swift: `addCleaner(name:)`, `updateCleaner(_:)`, `deleteCleaner(id:)` (plain deletion path for "no future jobs — plain deletion"; rebooking lands in US4), `addClient(name:)`, `updateClient(_:)`, `deleteClient(id:)`, and `bookJob(clientID:cleanersRequired:expectedLength:requestedDay:)throws -> Job` calling Rules.swift, persisting all-or-nothing. Make T017 pass. Depends on T009–T011, T013.

**Checkpoint**: US1 alone is deliverable: booking without conflicts + full record management, verified independently and by `swift test` (BookingTests).

---

## Phase 4: User Story 2 - Cleaners work their day in the field (Priority: P1)

**Goal**: The cleaner's day view and Arrive/Depart taps; "the elapsed time between the two taps is their time worked on the job."

**Independent Test**: "Assign jobs to a cleaner, perform Arrive/Depart taps, and verify the recorded per-cleaner worked time equals the difference between the taps, and that the cleaner's day view matches the back office's booking." (spec.md US2)

### Tests for User Story 2 (write first, must fail before implementation)

- [ ] T021 [P] [US2] Contract tests for field pages in tests/contract/test_field_pages.py: GET `/field/<cleaner_id>/today` ("assigned jobs with client, booked times, per-assignment state (FR-006)", US2-AC1), POST `/field/<cleaner_id>/jobs/<job_id>/arrive` and `/depart` — V5 (Arrive 8:05, Depart 12:05 → worked 4.0 h), US2-AC3/V6 (double Depart → "Error, nothing changes"), and edge cases: taps out of order/twice/"on a job not assigned to that cleaner -> error shown, nothing changes", same-instant taps allowed (contracts/backoffice-web.md).
- [ ] T022 [P] [US2] Unit tests for tap rules in tests/unit/test_rules_taps.py driving rules.py + store.py: state transitions `scheduled --first Arrive--> in_progress`, "Depart requires arrival set, departure unset", worked_min = departure − arrival to the minute, foreign-cleaner tap → error, and no store write on any failed tap (SC-007 "leaves the records exactly as they were").
- [ ] T023 [P] [US2] Swift XCTest for taps in CleanerApp/Tests/CleaningLogicTests/FieldTests.swift: `jobs(forCleaner:on:)` day view, `arrive(cleanerID:jobID:at:)`, `depart(cleanerID:jobID:at:)` replaying V5/V6 and the tap edge cases, expecting `tapOutOfOrder`/`wrongCleaner` throws (contracts/cleaner-logic-swift.md).

### Implementation for User Story 2

- [ ] T024 [US2] Implement the cleaner day page in webapp/templates/field_day.html ("rendered with the back office DB", plan.md): per assigned job show client name, booked times, per-assignment state (arrival/departure/worked), Arrive/Depart/Extend POST buttons wired to the field routes.
- [ ] T025 [US2] Implement the field handlers in webapp/cleaning/views.py: GET `/field/<cleaner_id>/today`, POST arrive/depart using rules.py tap validation via store.py ("Arrive requires state `scheduled`/`in_progress` with this assignment's arrival unset; Depart requires arrival set, departure unset"), state scheduled→in_progress on first arrival, error banner + no change on misuse (FR-006/FR-007). Make T021/T022 pass. Depends on T024.
- [ ] T026 [US2] Implement the Swift field API in CleanerApp/Sources/CleaningLogic/Store.swift: `jobs(forCleaner:on:) -> [Job]`, `arrive(cleanerID:jobID:at:) throws`, `depart(cleanerID:jobID:at:) throws` (worked_min derived on Depart, FR-007), validating against Rules.swift and throwing CleaningError per contract. Make T023 pass; depends only on T009–T011, T013 (Swift side, independent of the Python templates).

**Checkpoint**: US1 + US2 together form "the minimum viable loop": trustworthy per-cleaner worked time over conflict-free bookings.

---

## Phase 5: User Story 3 - Invoices are issued on completion and settled (Priority: P2)

**Goal**: Auto-invoice at last departure ($45/h per cleaner's worked time, per-line cent rounding), full-payment-only settlement, settled/unsettled visibility.

**Independent Test**: "Complete a job with known per-cleaner times and verify an invoice appears automatically, itemized per cleaner, with the cent-exact total of worked hours x $45; pay it in full and verify it becomes settled; attempt a partial payment and see it refused." (spec.md US3)

### Tests for User Story 3 (write first, must fail before implementation)

- [ ] T027 [P] [US3] Unit tests for invoice math and issuance in tests/unit/test_rules_invoice.py: US3-AC1 (A 4.0 h → "$180.00", B 3.5 h → "$157.50", total "$337.50"), "total = sum of the rounded lines" (Assumption), same-instant edge case "Arrive and Depart at the same instant -> allowed; that cleaner's invoice line is $0.00", issuance timing ("when a job whose first cleaner departed but whose second has not ... none exists yet" — US3-AC3/V9), invoice immutability ("issued invoices never change except `settled`, `payment_amount`, `payment_date`").
- [ ] T028 [P] [US3] Contract tests for invoice pages in tests/contract/test_invoice_pages.py: GET `/invoices` ("List with settled / unsettled status (FR-014)"), GET `/invoices/<id>` ("per-cleaner lines (worked time, $), total, issue moment, payment info"), POST `/invoices/<id>/pay` with amount (decimal): V8 (pay equal → settled; $337.49 → "mismatch refused unsettled"), V17 (pay already-settled → refused; pay id 99999 → refused, "no change, messages shown").
- [ ] T029 [P] [US3] Swift XCTest for invoicing in CleanerApp/Tests/CleaningLogicTests/BillingTests.swift: last-departure issuance (FR-011), `invoice(forJob:)`, `recordPayment(invoiceID:amount:at:)` replaying V7/V8/V17 expecting `paymentAmountMismatch`/`alreadySettled`/`notFound` throws (contracts/cleaner-logic-swift.md).

### Implementation for User Story 3

- [ ] T030 [US3] Implement issuance + settlement in the Python side: in webapp/cleaning/rules.py the `issue_invoice`/`record_payment` pure functions per D-6/D-7 ("Line per cleaner = round(worked_hours × 45, 2 cents) (round-half-up on the exact Decimal), total = sum of rounded lines"; "unknown invoice → error; already settled → error, nothing changes; amount ≠ total ... → refused"), and in webapp/cleaning/store.py completion of the job together with invoice creation "in the same atomic store write" (FR-011) setting Job.invoice_id "set at completion, same write".
- [ ] T031 [US3] Implement the invoice templates and routes in webapp/templates/ (invoices list/detail with settled status banner) and webapp/cleaning/views.py: GET `/invoices`, GET `/invoices/<id>`, POST `/invoices/<id>/pay` (FR-013/FR-014), error banner on refusals, no invoice mutation on failed payment. Make T028 pass (and T027 with T030). Depends on T030.
- [ ] T032 [US3] Implement the Swift billing API in CleanerApp/Sources/CleaningLogic/Store.swift: issuance hooked into the last `depart` ("last depart issues invoice atomically", FR-011 via Rules.swift invoice math + Rules/Store), `invoice(forJob:) -> Invoice?`, `recordPayment(invoiceID:amount:at:) throws` (full-equal only). Make T029 pass. Depends on T009–T011, T013.

**Checkpoint**: Booking → taps → invoice → settlement loop works end to end in both expressions; invoices are cent-exact and immutable.


---

## Phase 6: User Story 4 - Extensions and removals keep the schedule consistent (Priority: P2)

**Goal**: 20-minute extensions that cascade rebookings ("A cleaner who needs more time asks for it in 20-minute steps ... that later job — and anything it in turn bumps — is booked again by the booking rule, starting no earlier than 1 hour after the extended end"); delete-cleaner rebooking and delete-client cancellation with issued invoices never changing.

**Independent Test**: "Extend a job repeatedly and verify the chain of rebookings respects the booking rule and the 1-hour spacing with no overlap anywhere afterwards; delete a cleaner with future jobs and a client with future jobs and verify rebooking/cancellation while issued invoices remain untouched." (spec.md US4)

### Tests for User Story 4 (write first, must fail before implementation)

- [ ] T033 [P] [US4] Unit tests for extension cascade in tests/unit/test_rules_extension.py: US4-AC1 (job ends 12:00, later job 12:30, one 20-min extension → new end 12:20, "later job is rebooked at the earliest slot no earlier than 13:20"), US4-AC2 (every bumped job gets "the same booking rule (earliest slot on or after its minimum start, enough distinct free cleaners, inside 8:00–17:00 Mon–Fri)"), V11 ("Chain terminates"), V16 (extend a job ending 16:50 → "End 17:10 allowed; bumped rebookings still inside window (FR-008)"), abort+restore on infeasibility per D-4 ("If rebooking yields no feasible slot, abort the whole operation, restore the pre-operation schedule, and report").
- [ ] T034 [P] [US4] Unit tests for removals in tests/unit/test_rules_removals.py: US4-AC3 (delete cleaner → future jobs "rebooked onto remaining cleaners per the booking rule"), V12 (delete cleaner holding a future 2-cleaner job while <2 cleaners remain → "Reported, nothing changes"), US4-AC4 (delete client with future jobs + issued invoice → "the future jobs are cancelled and the issued invoice is unchanged"), edge case "Deleting a cleaner or client with no future jobs -> plain deletion", D-5 ("only future `scheduled` jobs" are cancelled in memory; store file may be amended solely by invoice-settlement writes, so compare invoices, not bytes).
- [ ] T035 [P] [US4] Contract tests in tests/contract/test_extension_removal_pages.py: POST `/field/<cleaner_id>/jobs/<job_id>/extend` ("+20 min step; cascades rebookings (FR-008/009)") and POST `/cleaners/<id>/delete` ("Delete (rebooks future jobs per rule; abort+report if any job unrebookable)") and `/clients/<id>/delete` ("delete cancels client's future jobs, invoices untouched") per contracts/backoffice-web.md.
- [ ] T036 [P] [US4] Swift XCTest for extension/removals in CleanerApp/Tests/CleaningLogicTests/ExtensionTests.swift: `extend(cleanerID:jobID:) throws` ("+20 min + cascade (FR-009)"), `deleteCleaner(id:) throws` ("rebooks future jobs or throws .notEnoughCleaners (nothing changes)"), `deleteClient(id:) throws` ("cancels future jobs; invoices untouched") replaying US4 scenarios and V10–V13 (contracts/cleaner-logic-swift.md).

### Implementation for User Story 4

- [ ] T037 [US4] Implement extension + cascade in webapp/cleaning/rules.py per research.md D-4 exactly: "+20 min on their job's end (no 17:00 cap for the extending job itself, FR-008)"; loop over "every later scheduled job on that cleaner's schedule starting < 60 min after the (possibly updated) end", chain "in start order; remove it, then rebook it by the D-3 algorithm with a minimum start = max(its current day, day of extended-end + 60 min)"; "re-apply the placement step to every successor whose spacing is violated, repeating until a full pass finds no violation"; on infeasibility restore the pre-operation schedule and return a report (FR-016). Extend the field route POST `/field/<cleaner_id>/jobs/<job_id>/extend` in webapp/cleaning/views.py and webapp/templates/field_day.html accordingly (contracts/backoffice-web.md). Make T033/T035 pass.
- [ ] T038 [US4] Implement delete-cleaner rebooking and delete-client cancellation in webapp/cleaning/rules.py + webapp/cleaning/store.py + the delete routes in webapp/cleaning/views.py per research.md D-5: per future scheduled job "(earliest start first), rebook by D-3 with minimum start = the job's current booked day/start; the deleted cleaner is removed from the candidate pool first"; "If any job finds no feasible slot ... abort the deletion, change nothing, and report it"; client delete cancels "only future `scheduled` jobs" and never touches invoices (FR-010). Make T034/T035 pass (with T037). Depends on T037 for shared rebook plumbing.
- [ ] T039 [US4] Implement the Swift extension/removal API in CleanerApp/Sources/CleaningLogic/Store.swift via Rules.swift: `extend(cleanerID:jobID:) throws` (+20 min + cascade), `deleteCleaner(id:) throws`, `deleteClient(id:) throws` per contracts/cleaner-logic-swift.md. Make T036 pass (T020's deleteCleaner gains the rebooking path). Depends only on T009–T011, T013 (mirrors T037–T038 rules).

**Checkpoint**: Field reality handled: running long never breaks the schedule; removals never strand jobs or touch issued invoices.

---

## Phase 7: User Story 5 - Utilization visibility (Priority: P3)

**Goal**: Per cleaner, "billable hours worked out of 8 per workday and out of 40 per week" shown to the back office.

**Independent Test**: "After a period of booked work, verify each cleaner's day and week totals equal the summed worked times within the 8 h / 40 h frame." (spec.md US5)

### Tests for User Story 5 (write first, must fail before implementation)

- [ ] T040 [P] [US5] Unit tests in tests/unit/test_rules_utilization.py per D-8: "day total = Σ worked minutes of C's departures on D ÷ 60 against 8 h (shown as x/8 h); week total = Σ worked minutes in D's calendar week (Mon–Sun containing D) against 40 h", "Only departed cleaners' worked times count", extensions may exceed the frames ("the frames are targets, not caps").
- [ ] T041 [P] [US5] Contract tests in tests/contract/test_utilization_page.py: GET `/utilization?day=YYYY-MM-DD` → "Per cleaner: day worked/8 h, week worked/40 h (FR-015)" 200 page (V19, contracts/backoffice-web.md).
- [ ] T042 [P] [US5] Swift XCTest in CleanerApp/Tests/CleaningLogicTests/UtilizationTests.swift: `utilizationReports(day:) -> [UtilizationReport]` replaying V19 with the same expected day/week totals as the Python side.

### Implementation for User Story 5

- [ ] T043 [US5] Implement the utilization computation in webapp/cleaning/rules.py (D-8) and the `/utilization?day=` handler in webapp/cleaning/views.py with a table template in webapp/templates/. Make T040/T041 pass.
- [ ] T044 [US5] Implement `utilizationReports(day:)` in CleanerApp/Sources/CleaningLogic/Store.swift via Rules.swift. Make T042 pass. Depends only on T009–T011, T013.

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Whole-system gates from spec's Success Criteria and the parity requirement.

- [ ] T045 [P] Implement the scripted audit workload in tests/audit/test_scenarios_audit.py per quickstart.md V18: "Scripted: 12 cleaners, 2 staff role ops, ~4.14 h ± 1.75 h job mix" → "Zero failures; audit invariants hold (tests/audit/)", asserting the 4 cross-entity invariants from data-model.md (gap ≥ 60 min both directions; scheduled jobs inside 8:00–17:00 Mon–Fri with the post-17:00 extension exemption; "∀ complete job ⇔ exactly one invoice, Σ lines total = Σ worked_h × $45 rounded per line"; "Settled invoice ⇒ payment_amount = total exactly, settled = true") after every mutating op — SC-001..SC-007.
- [ ] T046 [P] Implement the Swift parity replay in CleanerApp/Tests/CleaningLogicTests/FullReplayTests.swift: V20 — "Replay V1–V17 through `Store` in XCTest; Same results/errors as Python side" (quickstart.md), covering all US1–US5 acceptance scenarios + Edge Cases per the contracts/cleaner-logic-swift.md Parity gate.
- [ ] T047 Run `.venv/bin/pytest tests/` until fully green (quickstart.md "Run the tests") and fix any rule drift shared/rule-spec.md vs either implementation reveals.
- [ ] T048 Run `swift build && swift test --disable-sandbox` in CleanerApp/ until fully green (quickstart.md Setup; SwiftPM sandbox workaround per quickstart prerequisites).
- [ ] T049 [P] Run through all 20 validation scenarios V1–V20 in specs/001-cleaning-scheduling-billing/quickstart.md against the running app (`PORT=18080 .venv/bin/python webapp/app.py`) and record results; every scenario "matches its Expected column" per the Pass criteria.
- [ ] T050 [P] Update README.md at the repo root with the two quickstart commands, port policy (127.0.0.1, 18080–18089), the two-file local store layout, and the "two expressions, not connected" note.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories. T006→T007→T008 (Python chain), T009→T010→T011 (Swift chain) run in parallel across languages; T012 depends on nothing beyond T002/T008 shape; T013 last (cites both rule engines).
- **User Stories (Phase 3+)**: All depend on Foundational completion.
- **Polish (Phase 8)**: T045–T046 depend on the stories they audit; T047/T048 require everything before them; T049–T050 last.

### User Story Dependencies

- **US1 (P1)** and **US2 (P1)**: after Foundational; the spec pairs them as the MVP. US1's booking is the prerequisite for US2's taps in practice (taps act on booked jobs — US2-AC3/V6).
- **US3 (P2)**: "depends on booking (P1) and worked time (P1) existing first" (spec Why-this-priority) — deliver after US1 + US2.
- **US4 (P2)**: after US1 (reuses the booking rule) and after US3 (must prove "Issued invoices never change" and "invoices remain untouched" against real invoices). T038 depends on T037 (shared rebook primitive).
- **US5 (P3)**: needs worked times from US2's taps (it aggregates the same `worked_min`).
- Within each story: tests (T0xx test tasks) MUST be written and fail before their implementation tasks; Swift Store tasks (T026, T032, T039, T044, T020) depend only on T009–T011 + T013 and may run in parallel with the corresponding Python story tasks by a second worker.

### Critical path

T001 → {T006→T007→T008} → T013 → US1 (T016/T015 → T018 → T019) → US2 (T022/T021 → T024 → T025) → US3 (T027/T028 → T030 → T031) → US4 (T033/T034/T035 → T037 → T038) → US5 (T040/T041 → T043) → T047/T048 → T049.

### Parallel Opportunities

- T002/T003/T004/T005 (Setup) in parallel; the Python chain (T006–T008) vs the Swift chain (T009–T011) in parallel across two workers.
- All per-story test tasks ([P]) in parallel; Python story tasks vs the mirrored Swift Store task in the same story in parallel.
- After US1+US2+US3, US4 and US5 can proceed in parallel (different files: extension/removal logic vs utilization view) if staffing allows.

## Parallel Example: User Story 1

```bash
# Tests first, together (T014–T017):
Task: "Contract tests for cleaner/client pages in tests/contract/test_cleaner_client_pages.py"
Task: "Contract tests for booking and job CRUD in tests/contract/test_booking_pages.py"
Task: "Unit tests for the booking rule in tests/unit/test_rules_booking.py"
Task: "Swift XCTest for booking in CleanerApp/Tests/CleaningLogicTests/BookingTests.swift"
# Then Python impl (T018→T019) in parallel with Swift Store API (T020).
```

## Implementation Strategy

### MVP First (US1 + US2 — the spec pairs the two P1 stories as "the minimum viable loop")

1. Complete Phase 1 (Setup) and Phase 2 (Foundational — CRITICAL, blocks everything).
2. Deliver Phase 3 (US1): conflict-free earliest-slot booking + CRUD. Gate: `.venv/bin/pytest tests/unit tests/contract -k "booking or cleaner or client or job"` + `swift test` green.
3. Deliver Phase 4 (US2): taps + worked time. MVP = working booking-to-time-tracking loop.
4. Then US3 (invoicing/settlement), US4 (extensions/removals), US5 (utilization) as increments; each checkpoint re-runs the story's tests plus the audit invariants (T045 skeleton).

### Incremental Delivery

Each story phase is demoable against quickstart.md V-scenarios without touching the next story: US1 = V1–V4+V14, US2 = V5–V6+V15, US3 = V7–V9+V17, US4 = V10–V13+V16, US5 = V19, full parity = V18+V20.

---

## Validation Checklist (before reporting done)

- [ ] Every user story has tests + implementation tasks with exact file paths
- [x] Checklist format (checkbox, ID, labels, [P], file paths) verified for all 50 T-tasks (T001–T050, sequential, story labels in story phases only)
- [ ] Each story independently testable per its Independent Test quote
- [ ] Checklist format honored across T001–T050 (checkbox, ID, [P] where parallel, [USx] in story phases, file paths)
- [ ] All constraints quoted verbatim where they bind a task (540-min refusal, {1,2,3} headcount, 60-min symmetric spacing, 52-workday horizon — research.md D-3 says "52-workday horizon" / "up to a 52-workday horizon" while plan.md says "a bounded horizon of workdays (52 weeks)"; resolve in favor of research.md's 52 workdays, D-3 being the decision of record; $45/h half-up per line, total = Σ rounded lines, 8 h/40 h frames)

