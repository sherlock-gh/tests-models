# Test 2 on Terra's plan (run 1): milestones

Each build gets this plan (`plan/`, as `specs/001-cleaning-scheduling-billing/`) and builds one app: Python builds `backoffice/`, Swift builds `mobile/`. A milestone is the plan's tasks for that app in the phases below, one job, ending in a commit, and must pass its own hidden tests and every earlier milestone's. The exact interfaces are in `plan/contracts/exact-interfaces.md`.

| Milestone | Phases (user stories) | Python (`backoffice/`) | Swift (`mobile/`) |
|---|---|---|---|
| 1 | Setup, foundation, records and booking | T001, T003, T005, T007, T009, T011, T013, T015, T017, T018 | T002, T004, T006, T008, T010, T012, T014, T016 |
| 2 | Field work and extensions | T019, T021, T023, T025 | T020, T022, T024, and billing: T027, T029, T031 |
| 3 | Invoices and payment | T026, T028, T030, T032 | removals and utilization: T034, T036, T038 |
| 4 | Removals, utilization and polish | T033, T035, T037, T039–T041 | — |

Swift has three milestones: its billing joins milestone 2 and its removals and utilization make milestone 3, as it has no server or page.
