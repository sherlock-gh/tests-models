# Test 2 on Flash-Next's iteration 3 plan (run 1, the only fit local plan): milestones

Every model builds from this plan (`plan/`, as `specs/001-cleaning-scheduling-billing/`), one app a build: Python builds `desktop/`, Swift builds `CleaningKit/`. A milestone is the plan's tasks for that app in the phases below, one job, ending in a commit, and must pass its own hidden tests and every earlier milestone's. The exact interfaces are in `plan/contracts/exact-interfaces.md`.

| Milestone | Phases (user stories) | Python (`desktop/`) | Swift (`CleaningKit/`) |
|---|---|---|---|
| 1 | Setup, foundation, booking (US1) | T001, T003–T007, T011, T012, T014–T017, T019 | T002, T008–T011, T013, T018 |
| 2 | Taps and invoices (US2), settlement (US5) | T020, T022, T023, T034, T036 | T021, T024, T025, T035, T037 |
| 3 | More time (US3), records and deletions (US4) | T026, T028, T030, T032 | T027, T029, T031, T033 |
| 4 | Utilization (US6), polish | T038, T040, T042–T044, T046, T047 | T039, T041, T045 |

T011's seed helper has a half in each app; T043 (cross-app parity) is a Python file.
