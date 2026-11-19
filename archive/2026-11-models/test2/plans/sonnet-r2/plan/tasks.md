---

description: "Task list for scheduling and billing for a house-cleaning business"
---

# Tasks: Scheduling and Billing for a House-Cleaning Business

**Input**: Design documents from `/specs/001-cleaning-scheduling-billing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (operations.md, http-api.md, conformance-scenarios.md), quickstart.md

**Tests**: Included. plan.md and the spec's success criteria (SC-002, SC-003, SC-007) require unit, conformance (C1–C18) and a seeded stress test in both expressions.

**Organization**: Grouped by user story. Each story delivers both expressions: desktop (Python, `desktop/`) and mobile logic (Swift, `mobile/`). The two share no code, only contracts and conformance scenarios.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story (US1–US6)
- Money is integer cents, time is whole minutes (schedule) / seconds (worked); no floating point.

## Path Conventions

- Desktop: `desktop/cleaning/{rules,store,service,server}.py`, `desktop/cleaning/static/`, `desktop/seed.py`, `desktop/tests/`
- Mobile: `mobile/Package.swift`, `mobile/Sources/CleaningCore/`, `mobile/Tests/CleaningCoreTests/`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create directory structure per plan.md: `desktop/cleaning/static/`, `desktop/tests/`, `mobile/Sources/CleaningCore/`, `mobile/Tests/CleaningCoreTests/`, `data/` (with `.gitignore` entry for `data/*.json`)
- [ ] T002 [P] Add `desktop/__init__.py`, `desktop/cleaning/__init__.py`, `desktop/tests/__init__.py` so `python3 -m unittest discover desktop/tests` and `python3 -m desktop.cleaning.server` work (Python 3.11+, stdlib only)
- [ ] T003 [P] Create `mobile/Package.swift` (swift-tools 5.9, platforms iOS 16 / macOS 13, library `CleaningCore`, test target `CleaningCoreTests`, no third-party dependencies)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, errors, atomic persistence and shared test helpers used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Define error type with codes `invalid_input`, `not_found`, `unschedulable`, `invalid_state`, `payment_mismatch` and `{code, message}` in `desktop/cleaning/service.py` (class `CleaningError`)
- [ ] T005 [P] Define Swift `CleaningError` (codes identical to T004, carries message) in `mobile/Sources/CleaningCore/Errors.swift`
- [ ] T006 [P] Implement data model per data-model.md as plain dataclasses/dicts (Cleaner, Client, Job, TimeEntry, Invoice, Payment; ids "integer, unique, never reused" via a persisted next-id counter) in `desktop/cleaning/store.py`
- [ ] T007 [P] Implement Codable models per data-model.md (same fields and rules as T006; dates ISO `YYYY-MM-DD`, schedule times minutes from midnight, Arrive/Depart ISO timestamps to the second, money cents) in `mobile/Sources/CleaningCore/Models.swift`
- [ ] T008 Implement JSON load/save with atomic write (temp file + rename after every successful change; missing file → empty state) in `desktop/cleaning/store.py` (depends on T006)
- [ ] T009 Implement JSON load/save with atomic write (`Data.write(options: .atomic)` or temp+rename; same JSON shape as T008) in `mobile/Sources/CleaningCore/Store.swift` (depends on T007)
- [ ] T010 Implement validate-then-commit pattern in `desktop/cleaning/service.py`: every operation works on a deep copy of state and swaps/saves only on success, so errors leave data unchanged (FR-020) (depends on T004, T008)
- [ ] T011 Implement the same copy-then-commit pattern in `mobile/Sources/CleaningCore/Service.swift` (class `CleaningService`, throws `CleaningError`) (depends on T005, T009)
- [ ] T012 [P] Add shared test helper (fixture builder: N cleaners, clients, temp data file; Monday = 2026-11-16) in `desktop/tests/helpers.py`
- [ ] T013 [P] Add the same fixture helper in `mobile/Tests/CleaningCoreTests/TestHelpers.swift`

**Checkpoint**: Foundation ready; user stories can begin.

---

## Phase 3: User Story 1 - Book a job without conflicts (Priority: P1) 🎯 MVP

**Goal**: Book a job (1–3 cleaners, length, requested day) into the earliest conflict-free slot with system-chosen cleaners.

**Independent Test**: Create cleaners, a client and several jobs; each lands in the earliest valid slot within 8:00–17:00, Mon–Fri, no overlaps (C1–C6).

### Tests for User Story 1

- [ ] T014 [P] [US1] Conformance tests C1–C6 and unit tests (weekend → Monday, exactly 540 min books 8:00–17:00, 541 refused, slot ending after 17:00 moves to next day, cleanersNeeded 0/4 → `invalid_input`, 13 needed with 12 cleaners → `unschedulable`, refusal changes nothing) in `desktop/tests/test_booking.py`
- [ ] T015 [P] [US1] Same conformance C1–C6 and unit tests in `mobile/Tests/CleaningCoreTests/BookingTests.swift`
- [ ] T016 [P] [US1] Brute-force per-minute oracle for earliest slot (research D5) and seeded randomized booking test (lengths ~N(4.14, 1.75) clamped to (0, 540] min) asserting zero overlaps and earliest-slot match, in `desktop/tests/test_stress.py`
- [ ] T017 [P] [US1] Same oracle and seeded randomized booking test in `mobile/Tests/CleaningCoreTests/StressTests.swift`

### Implementation for User Story 1

- [ ] T018 [US1] Implement pure booking rules in `desktop/cleaning/rules.py`: weekend → next Monday; candidate starts = 8:00 and each cleaner's job end + 60 on that day; choose first start where ≥ n cleaners are free for [start−60, start+L+60) and end ≤ 17:00 (1020); lowest-id cleaners; scan bounded to 366 days; "lengthMinutes integer > 0 and ≤ 540", "cleanersNeeded integer 1, 2 or 3"; cancelled jobs ignored
- [ ] T019 [US1] Implement the same booking rules in `mobile/Sources/CleaningCore/Rules.swift` with identical tie-breaks
- [ ] T020 [US1] Implement `book_job` (clientId "must reference an existing client"; errors `invalid_input` / `not_found` / `unschedulable`) in `desktop/cleaning/service.py` (depends on T018)
- [ ] T021 [US1] Implement `bookJob` in `mobile/Sources/CleaningCore/Service.swift` (depends on T019)

**Checkpoint**: Booking works and is verified in both expressions (MVP).

---

## Phase 4: User Story 2 - Manage cleaners, clients and jobs (Priority: P1)

**Goal**: CRUD on cleaners, clients, jobs with safe delete rules; desktop HTTP API and page.

**Independent Test**: CRUD each type; delete a cleaner with future jobs (re-booked) and a client with future jobs (cancelled, invoices unchanged); bad input/missing record → visible error, no change (C7, C8).

### Tests for User Story 2

- [ ] T022 [P] [US2] CRUD, validation ("name required, non-blank"), not_found and conformance C7/C8 tests (including cleaner delete refused all-or-nothing when a job cannot be re-booked) in `desktop/tests/test_records.py`
- [ ] T023 [P] [US2] Same tests in `mobile/Tests/CleaningCoreTests/RecordsTests.swift`
- [ ] T024 [P] [US2] HTTP API tests (status codes, `{"error": {"code","message"}}` body, server still responds after errors, 500 on unexpected exception leaves data unchanged) in `desktop/tests/test_server.py`

### Implementation for User Story 2

- [ ] T025 [US2] Implement cleaner and client create/update/get/list/delete in `desktop/cleaning/service.py` (name "required, non-blank"; address "optional text"; client delete cancels not-started jobs, keeps in-progress/complete jobs and invoices)
- [ ] T026 [US2] Implement updateJob / deleteJob (not-started only, else `invalid_state`; update re-books by the booking rule) and listJobs/getJob in `desktop/cleaning/service.py`
- [ ] T027 [US2] Implement cleaner delete: remove cleaner, re-book each not-started job chronologically via booking rule; if any fails refuse whole delete with `unschedulable` naming the job and change nothing (research D7) in `desktop/cleaning/service.py` (depends on T025, T026)
- [ ] T028 [US2] Implement the same record operations (T025–T027) in `mobile/Sources/CleaningCore/Service.swift`
- [ ] T029 [US2] Implement HTTP server in `desktop/cleaning/server.py` with `http.server` bound to `127.0.0.1`, routes for cleaners/clients/jobs CRUD per contracts/http-api.md, JSON error mapping (4xx/500), CLI `--data` and `--port` (default 8000), never exiting on request errors (depends on T025–T027)
- [ ] T030 [P] [US2] Build back-office page `desktop/cleaning/static/index.html`, `app.js`, `style.css`: forms and lists for cleaners, clients, jobs (booking form), visible error banner on every failure; served at `GET /` (depends on T029)
- [ ] T031 [P] [US2] Create synthetic data generator `desktop/seed.py` (`--data PATH`; 12 cleaners, sample clients, fake addresses only)

**Checkpoint**: US1 and US2 both work; back office can manage everything via page/API.

---

## Phase 5: User Story 3 - Record time in the field (Priority: P2)

**Goal**: Cleaner sees their day and records Arrive/Depart.

**Independent Test**: Day view lists exactly the cleaner's jobs in time order; Arrive then Depart stores time worked; invalid sequences error (C9).

### Tests for User Story 3

- [ ] T032 [P] [US3] Tests for day view ordering, arrive/depart, depart-before-arrive, double arrive, arrive on unassigned job (all `invalid_state`/`invalid_input`, no change), job → `in_progress` on first arrive, depart earlier than arrive refused, in `desktop/tests/test_field.py`
- [ ] T033 [P] [US3] Same tests in `mobile/Tests/CleaningCoreTests/FieldTests.swift`

### Implementation for User Story 3

- [ ] T034 [US3] Implement `cleaner_day`, `arrive`, `depart` in `desktop/cleaning/service.py` ("arrivedAt set once; second Arrive refused"; "departedAt requires arrivedAt, must be ≥ arrivedAt; set once"; secondsWorked = departedAt − arrivedAt; cleaner must be assigned; cancelled/complete jobs refused)
- [ ] T035 [US3] Implement `cleanerDay`, `arrive`, `depart` in `mobile/Sources/CleaningCore/Service.swift`
- [ ] T036 [US3] Add routes `GET /api/cleaners/{id}/day`, `POST /api/jobs/{id}/arrive` and `/depart` in `desktop/cleaning/server.py`, and a day-view/arrive/depart panel in `desktop/cleaning/static/app.js` (depends on T034)

**Checkpoint**: Time recording works independently of invoicing.

---

## Phase 6: User Story 4 - Invoice on completion and track settlement (Priority: P2)

**Goal**: Invoice issued when last cleaner departs; pay in full only; settled status visible.

**Independent Test**: Two-cleaner job 4h00m/4h10m → invoice 18000 + 18750 = 36750 cents; partial payment refused; full payment settles; repeat refused (C10–C12, C17).

### Tests for User Story 4

- [ ] T037 [P] [US4] Tests C10, C11, C12, C17 plus rounding ((seconds × 5 + 2) // 4), snapshot immutability after client/cleaner delete, settled filter, in `desktop/tests/test_billing.py`
- [ ] T038 [P] [US4] Same tests in `mobile/Tests/CleaningCoreTests/BillingTests.swift`

### Implementation for User Story 4

- [ ] T039 [US4] Add charge calculation `charge_cents(seconds) = (seconds * 5 + 2) // 4` to `desktop/cleaning/rules.py`
- [ ] T040 [US4] Add the same integer charge calculation to `mobile/Sources/CleaningCore/Rules.swift`
- [ ] T041 [US4] Issue invoice in `depart` when last assigned cleaner departs (job → `complete`; "one invoice per job"; snapshot clientName and cleanerName per line; totalCents = sum of line charges; settled false) and implement `list_invoices(settled=None)`, `get_invoice`, `pay_invoice` ("amountCents must equal invoice totalCents exactly" else `payment_mismatch`; settled invoice → `invalid_state`) in `desktop/cleaning/service.py` (depends on T034, T039)
- [ ] T042 [US4] Implement the same invoicing and payment in `mobile/Sources/CleaningCore/Service.swift` (depends on T035, T040)
- [ ] T043 [US4] Add routes `GET /api/invoices[?settled=]`, `GET /api/invoices/{id}`, `POST /api/invoices/{id}/pay` in `desktop/cleaning/server.py` and an invoices view with settled/unsettled indicator and pay form in `desktop/cleaning/static/app.js` (depends on T041)

**Checkpoint**: Full field-to-cash flow works.

---

## Phase 7: User Story 5 - Request more time on a job (Priority: P3)

**Goal**: 20-minute extensions with cascading re-booking.

**Independent Test**: Back-to-back jobs for one cleaner; extend the first; later job moves, no overlaps anywhere (C13–C15, C18).

### Tests for User Story 5

- [ ] T044 [P] [US5] Tests C13, C14, C15, cascade of bumped jobs, extension of complete/cancelled job refused, all-or-nothing on failure, in `desktop/tests/test_extension.py`
- [ ] T045 [P] [US5] Same tests in `mobile/Tests/CleaningCoreTests/ExtensionTests.swift`
- [ ] T046 [US5] Extend the stress tests (T016/T017) with extensions and deletes (≥ 1,000 seeded operations, invariants after each: no overlaps, earliest slot vs oracle) in `desktop/tests/test_stress.py` and `mobile/Tests/CleaningCoreTests/StressTests.swift` (C18)

### Implementation for User Story 5

- [ ] T047 [US5] Implement extension with worklist cascade in `desktop/cleaning/rules.py` and `service.py` (`request_extension`: minutes "positive multiple of 20" else `invalid_input`; complete/cancelled → `invalid_state`; later jobs of each assigned cleaner starting < 60 min after new end are un-booked and re-booked with earliest-start floor of new end + 60 on that day; repeat until stable; endMinute may exceed 1020; computed on a copy, committed only if all succeed)
- [ ] T048 [US5] Implement the same extension and cascade in `mobile/Sources/CleaningCore/Rules.swift` and `Service.swift`
- [ ] T049 [US5] Add route `POST /api/jobs/{id}/extend` in `desktop/cleaning/server.py` and an extend control in `desktop/cleaning/static/app.js` (depends on T047)

**Checkpoint**: Schedule absorbs overruns without conflicts.

---

## Phase 8: User Story 6 - See cleaner utilization (Priority: P3)

**Goal**: Per-cleaner billable hours out of 8 (day) and 40 (week, Mon–Sun).

**Independent Test**: With recorded time, day/week figures match (C16).

### Tests for User Story 6

- [ ] T050 [P] [US6] Test C16 (6 of 8 = 75%; 30 of 40 = 75%), attribution to the Arrive date, week boundaries Mon–Sun, in `desktop/tests/test_utilization.py`
- [ ] T051 [P] [US6] Same tests in `mobile/Tests/CleaningCoreTests/UtilizationTests.swift`

### Implementation for User Story 6

- [ ] T052 [US6] Implement `utilization(cleaner_id, date)` in `desktop/cleaning/service.py` (hours and percentage of 8 for the day and of 40 for the Monday–Sunday week; sum of secondsWorked for entries whose arrivedAt is that date)
- [ ] T053 [US6] Implement `utilization` in `mobile/Sources/CleaningCore/Service.swift`
- [ ] T054 [US6] Add route `GET /api/utilization?date=` in `desktop/cleaning/server.py` and a utilization table in `desktop/cleaning/static/app.js` (depends on T052)

**Checkpoint**: All user stories functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T055 [P] Verify both suites implement every scenario C1–C18 (checklist comment at top of `desktop/tests/test_conformance_index.py` and `mobile/Tests/CleaningCoreTests/ConformanceIndexTests.swift`), fixing any divergence between the two implementations
- [ ] T056 Run `python3 -m unittest discover desktop/tests` and `cd mobile && swift test`; fix failures
- [ ] T057 Run the quickstart.md validation: seed, start server, exercise book/arrive/depart/pay/extend/utilization and an invalid request; confirm the server keeps responding and data is unchanged on errors (SC-003)
- [ ] T058 [P] Add a short `README.md` at repo root with run instructions copied from quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → user stories → **Polish (9)**
- US1 first (MVP). US2 needs US1's booking (re-book on delete, updateJob). US3 needs a booked job (US1). US4 needs US3 (depart triggers invoice). US5 needs US1 booking rules. US6 needs US3 time entries.
- Desktop and mobile tracks inside each story are independent of each other and can proceed in parallel.

### Within Each Story

- Tests before implementation (write, see fail); rules before service; service before server routes/UI.
- Tasks touching the same file (`service.py`, `Service.swift`, `server.py`, `app.js`) are sequential, hence not marked [P].

### Parallel Opportunities

- Phase 1 T002/T003; Phase 2 T004–T007, T012/T013
- Per story, the desktop test, Swift test and stress tasks (all [P])
- After US1: US5 rule work can proceed alongside US2/US3 if file conflicts in `service.py` are coordinated

### Parallel Example: User Story 1

```text
Task: "Conformance tests C1–C6 in desktop/tests/test_booking.py"
Task: "Same tests in mobile/Tests/CleaningCoreTests/BookingTests.swift"
Task: "Oracle + randomized booking test in desktop/tests/test_stress.py"
Task: "Oracle + randomized booking test in mobile/Tests/CleaningCoreTests/StressTests.swift"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phases 1–2, then Phase 3 (booking in both expressions)
2. Stop and validate C1–C6 and the booking stress test

### Incremental Delivery

1. Add US2 (records, API, page) → US3 (field time) → US4 (invoicing, payment) → US5 (extensions) → US6 (utilization)
2. After each story, run both suites; each story must not break the earlier ones

---

## Notes

- Keep the two implementations in step: any rule change updates `contracts/operations.md` and the conformance scenarios first.
- All data is synthetic; no network services, accounts or third-party packages.
- Commit after each task or logical group.
