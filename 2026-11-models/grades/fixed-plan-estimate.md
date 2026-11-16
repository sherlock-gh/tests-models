# Effort estimate

Basis: `problem.md`, `specs/001-cleaning-scheduling-billing/{spec,plan,tasks}.md` and contracts. The 58 tasks split as roughly 33 desktop (Python, local HTTP server, web page), 22 mobile (Swift package, no UI), and 3 shared polish tasks (T055–T058: conformance check, full test run, quickstart, README). The stress-test task T046 is split between the two. Human hours assume a competent developer who knows the language and reads the spec once. Token counts assume an AI coding agent working through tasks.md and iterating on test failures. They count input and output tokens summed over all turns, including re-reading files and test output.

## Desktop

Human hours: 44
Tokens: 950000

How I reached them:
- Setup, errors, data model, JSON store with atomic write, copy-then-commit pattern (T001, T002, T004, T006, T008, T010, T012): about 5 h.
- Booking rules (weekend roll, earliest slot, 1 h gap, 8:00–17:00, 540-minute limit) plus the brute-force oracle and randomized test (T014, T016, T018, T020): about 8 h. This is the hardest logic. The earliest-slot search over cleaners and days needs careful tie-breaks.
- Records CRUD, cleaner-delete re-booking that is all-or-nothing, job update and delete (T022, T025–T027): about 6 h.
- HTTP server, error mapping with no crash, API tests (T024, T029): about 5 h.
- Back-office page for cleaners, clients, jobs, invoices, utilization and the day view (T030, T036, T043, T049, T054): about 8 h of plain HTML and JS, with no framework.
- Time tracking, invoicing with integer rounding, payment, settlement filter (T032, T034, T037, T039, T041): about 5 h.
- Extension with cascade and the 1,000-operation stress test (T044, T046 half, T047): about 5 h.
- Utilization (T050, T052): about 1.5 h.
- Seed script, shared polish and quickstart run (T031, T055–T058): about 2.5 h.
- Total is about 46 h. I rounded to 44 h to allow for reuse of the tests and helpers.

Tokens: about 33 tasks at 15–20k tokens of generated code and tests each, about 550k. Debugging cycles, especially the cascade and the oracle, add about 250k. Re-reading the spec and contracts and running the server for verification add about 150k. The total is about 950k.

## Mobile

Human hours: 30
Tokens: 700000

How I reached them:
- Package.swift, error type, Codable models, store, copy-then-commit service, test helpers (T003, T005, T007, T009, T011, T013): about 4.5 h.
- Booking rules, bookJob, oracle and randomized tests (T015, T017, T019, T021): about 6 h. This is a port of the desktop logic, so the design is already settled. The work is in matching tie-breaks exactly.
- Records CRUD, job update and delete, cleaner-delete re-booking (T023, T028): about 4 h.
- Field operations: day view, arrive, depart (T033, T035): about 2.5 h.
- Invoicing, payment, rounding (T038, T040, T042): about 3.5 h.
- Extension and cascade, extended stress test (T045, T046 half, T048): about 5 h.
- Utilization (T051, T053): about 1.5 h.
- Shared polish and conformance check on the Swift side: about 1 h.
- There is no UI and no server. That makes it lighter than desktop despite Swift's stricter typing and its Codable and date handling.
- Total is about 28 h. I rounded to 30 h for Swift build and test friction.

Tokens: about 22 tasks at 15–20k tokens each, about 380k. Swift compiler errors and `swift test` iterations add about 220k. Reading the Python implementation and contracts for parity adds about 100k. The total is about 700k.

## Caveats

- Both figures cover implementation and tests only. They exclude requirements work, which is already done in the spec, plan and tasks.
- The Mobile figures assume the desktop design is already settled. Built alone, Mobile would cost roughly 25% more.
- The token counts are order-of-magnitude estimates. The uncertainty is about ±40%.
