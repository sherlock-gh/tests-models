---
description: "Implementation tasks for cleaning scheduling and billing"
---

# Tasks: Cleaning Scheduling and Billing

**Input**: `specs/001-cleaning-scheduling-billing/plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Both independent expressions have automated acceptance scenarios as specified in the plan and quickstart. Write each story's tests before its implementation and run them against isolated temporary stores.

## Phase 1: Setup

- [ ] T001 Create the Python package and standard-library test discovery structure in `backoffice/cleaning/__init__.py` and `backoffice/tests/__init__.py`.
- [ ] T002 [P] Initialize the Swift 5.9+ library and XCTest target in `mobile/Package.swift`, `mobile/Sources/CleaningLogic/`, and `mobile/Tests/CleaningLogicTests/`.

## Phase 2: Foundational

**Purpose**: Independent local stores and common domain primitives required by every story.

- [ ] T003 Define Python domain records in `backoffice/cleaning/models.py`: Cleaner and Client have ID, name, active/deleted marker; Job has ID, client ID, requested day, expected duration, required cleaner count, scheduled start and end, status; Assignment has Job ID, cleaner ID, arrival instant, departure instant. Preserve these constraints: "Exactly one client; one to three assignments.", "Duration is positive and at most nine hours.", "Normal scheduled intervals are on one weekday between 08:00 and 17:00; an active job's extended end can exceed 17:00.", "Unique per job and cleaner.", and "Arrival and departure are initially absent; departure requires a prior arrival and cannot precede it."
- [ ] T004 [P] Define equivalent Swift Codable domain records in `mobile/Sources/CleaningLogic/Models.swift` with the same fields and constraints as T003, including actual elapsed time and retained historical identities.
- [ ] T005 Implement configurable business time zone, injectable clock, unambiguous instants, and domain errors in `backoffice/cleaning/context.py`.
- [ ] T006 [P] Implement equivalent time zone, clock injection, instants, and usable domain errors in `mobile/Sources/CleaningLogic/Context.swift`.
- [ ] T007 Implement versioned JSON storage in `backoffice/cleaning/store.py`: serialize access, stage complete mutations in memory, validate, and atomically replace the configurable local file only on success.
- [ ] T008 [P] Implement independent versioned JSON storage in `mobile/Sources/CleaningLogic/Store.swift` with serialized access, staged mutations, atomic replacement, and configurable file path.
- [ ] T009 Verify failed mutations preserve persisted bytes and a later valid mutation succeeds, including concurrent access, in `backoffice/tests/test_store.py`.
- [ ] T010 [P] Verify the equivalent isolated-store atomicity and serialized access in `mobile/Tests/CleaningLogicTests/StoreTests.swift`.

## Phase 3: User Story 1 - Maintain records and book work (P1) 🎯 MVP

**Goal**: Maintain cleaners, clients and jobs and book the earliest eligible interval in both independent expressions.

**Independent test**: Create, retrieve, update and delete records; book jobs with one to three cleaners and varied durations; inspect schedules and verify invalid operations leave state unchanged.

- [ ] T011 [P] [US1] Write Python acceptance tests for record CRUD, earliest continuous-time booking, staffing, both-sided one-hour gaps, 17:00 equality, weekends, fresh-booking updates and atomic invalid requests in `backoffice/tests/test_booking.py`.
- [ ] T012 [P] [US1] Write equivalent Swift acceptance tests using its own temporary store in `mobile/Tests/CleaningLogicTests/BookingTests.swift`.
- [ ] T013 [P] [US1] Implement Python earliest-slot search in `backoffice/cleaning/scheduling.py`: weekday 08:00–17:00, candidate boundaries and lower bounds, one-hour gaps on both sides, deterministic cleaner ID ties, and rejection of invalid duration or insufficient cleaners.
- [ ] T014 [P] [US1] Implement equivalent Swift booking search in `mobile/Sources/CleaningLogic/Scheduling.swift` without a fixed search horizon or time grid.
- [ ] T015 [US1] Implement Python cleaner, client and job CRUD and transactional booking/update in `backoffice/cleaning/records.py`, retaining historical records and rejecting missing or invalid inputs.
- [ ] T016 [P] [US1] Implement equivalent callable Swift CRUD and booking operations in `mobile/Sources/CleaningLogic/Records.swift`.
- [ ] T017 [US1] Expose local Python HTTP record and schedule operations with recoverable errors and configurable store in `backoffice/server.py`.
- [ ] T018 [US1] Build record maintenance, booking and schedule views with visible errors in `backoffice/static/index.html` and `backoffice/static/app.js`.

## Phase 4: User Story 2 - Record work and handle extensions (P1)

**Goal**: Show assigned work, record arrival and departure, and atomically cascade extension rebookings.

**Independent test**: Seed a schedule, view a cleaner's chosen day, record arrival and departure, and extend an active job through a chain of rebookings, including after 17:00.

- [ ] T019 [P] [US2] Write Python tests for assigned-day listing, ordered one-time arrival/departure, 20-minute extensions, multi-cleaner cascades, after-hours end and atomic failures in `backoffice/tests/test_work.py`.
- [ ] T020 [P] [US2] Write equivalent Swift cleaner contract and cascade tests in `mobile/Tests/CleaningLogicTests/WorkTests.swift`.
- [ ] T021 [P] [US2] Implement Python deterministic staged cascading rebooking in `backoffice/cleaning/rebooking.py`, preserving displacement lower bounds and normal booking rules.
- [ ] T022 [P] [US2] Implement equivalent Swift cascade in `mobile/Sources/CleaningLogic/Rebooking.swift`.
- [ ] T023 [US2] Implement assigned-day listing, assignment validation, clock-based arrival/departure, actual elapsed time and positive 20-minute extension operations in `backoffice/cleaning/work.py`; stage completion for invoice issuance in US3.
- [ ] T024 [P] [US2] Expose equivalent callable cleaner operations and errors in `mobile/Sources/CleaningLogic/Work.swift`; stage completion for invoice issuance in US3.
- [ ] T025 [US2] Wire work and extension operations into the local HTTP interface in `backoffice/server.py` so the Python expression enforces the same domain rules.

## Phase 5: User Story 3 - Issue and settle invoices (P1)

**Goal**: Issue a preserved invoice atomically on the last departure and accept exactly one full payment.

**Independent test**: Complete a seeded multi-cleaner job with different elapsed times, inspect the invoice, and try partial, exact and repeated payments; delete its client and verify the snapshot remains intact.

- [ ] T026 [P] [US3] Write Python tests for last-departure issuance, individual elapsed times, one-time half-up total rounding, immutable snapshots, full payment and atomic rejection in `backoffice/tests/test_billing.py`.
- [ ] T027 [P] [US3] Write equivalent Swift invoice and payment tests in `mobile/Tests/CleaningLogicTests/BillingTests.swift`.
- [ ] T028 [P] [US3] Add Python Invoice and Payment records in `backoffice/cleaning/billing.py` with ID, job ID, issued instant, client identity snapshot, line snapshots, total in cents, settlement status, and Payment ID, invoice ID, amount in cents, recorded instant; enforce "Exactly one invoice per completed job.", "At most one per invoice; amount equals its full total.", and "Total is the sum of actual elapsed cleaner time at $45/hour, rounded once to the nearest cent."
- [ ] T029 [P] [US3] Add equivalent Swift invoice and payment records and constraints in `mobile/Sources/CleaningLogic/Billing.swift`.
- [ ] T030 [US3] Integrate Python last-departure completion with atomic invoice snapshots, integer-precision half-up billing, invoice review and exact single payment in `backoffice/cleaning/work.py` and `backoffice/cleaning/billing.py`.
- [ ] T031 [P] [US3] Integrate equivalent Swift completion, snapshots, billing and payment operations in `mobile/Sources/CleaningLogic/Work.swift` and `mobile/Sources/CleaningLogic/Billing.swift`.
- [ ] T032 [US3] Expose invoice review and payment in `backoffice/server.py` and add invoice, settlement and error views in `backoffice/static/index.html` and `backoffice/static/app.js`.

## Phase 6: User Story 4 - Recover schedules after removals and review utilization (P2)

**Goal**: Atomically recover future schedules on removals and show daily and weekly billable utilization.

**Independent test**: Remove a cleaner and a client with future jobs, check rebooking, cancellation and unchanged invoices, then compare completed work against eight-hour days and 40-hour weeks.

- [ ] T033 [P] [US4] Write Python tests for future-only cleaner rebooking, client cancellation, preserved in-progress work and invoice history, unsatisfiable rollback, and day/week utilization including midnight splits in `backoffice/tests/test_removals_utilization.py`.
- [ ] T034 [P] [US4] Write equivalent Swift removal and utilization tests in `mobile/Tests/CleaningLogicTests/RemovalsUtilizationTests.swift`.
- [ ] T035 [P] [US4] Implement Python atomic cleaner removal and client removal in `backoffice/cleaning/removals.py`: rebook unstarted future jobs or roll back, cancel a removed client's future jobs, and retain in-progress and historical records.
- [ ] T036 [P] [US4] Implement equivalent Swift removal operations in `mobile/Sources/CleaningLogic/Removals.swift`.
- [ ] T037 [P] [US4] Implement Python invoiced-work utilization with local-day splitting, Monday–Sunday weeks and eight/40-hour denominators in `backoffice/cleaning/utilization.py`.
- [ ] T038 [P] [US4] Implement equivalent Swift utilization in `mobile/Sources/CleaningLogic/Utilization.swift`.
- [ ] T039 [US4] Connect removal and utilization operations to `backoffice/server.py` and show utilization in `backoffice/static/index.html` and `backoffice/static/app.js`.

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T040 Document configuration, independent stores, server startup, Swift integration and test commands in `README.md`.
- [ ] T041 Run the complete Python and Swift suites and desktop walkthrough in `specs/001-cleaning-scheduling-billing/quickstart.md`; resolve discrepancies against the documented contracts.

## Dependencies & Execution Order

- Setup → Foundational → US1 → US2 → US3 → US4 → Polish is the recommended incremental path.
- US2 uses US1's booking and record primitives; US3 uses US2's departure flow; US4 uses US1 booking, US2 cascades, and US3 historical invoices. Each story's independent test can seed prerequisite state without running earlier story walkthroughs.
- Within each story, write tests first; implement models and domain logic before integration. Tasks sharing files or depending on another task's output must be sequenced.

### Parallel Opportunities

- T001 and T002 can run together; after setup, Python and Swift foundation tasks can proceed in parallel, respecting their own prerequisites.
- US1: T011 and T012, then T013 and T014, can run together; T015 and T016 follow their respective schedulers.
- US2: T019 and T020, then T021 and T022, can run together; T023 and T024 follow their respective cascades.
- US3: T026 and T027, then T028 and T029, can run together; T030 and T031 follow their respective models.
- US4: T033 and T034 can run together; T035–T038 operate on separate files after the earlier stories and tests are ready.

## Implementation Strategy

1. Complete setup and foundation, then implement and independently validate US1 as the MVP.
2. Add US2, US3 and US4 in dependency order, validating each increment in both independent stores.
3. Run the full quickstart and browser walkthrough, including recoverable errors and preservation of persisted state after failures.
