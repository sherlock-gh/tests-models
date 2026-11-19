# Test 2: milestones

Each build gets the fixed plan (`plan/`, as `specs/001-cleaning-scheduling-billing/`) and builds one app: Python builds `desktop/`, Swift builds `mobile/`. A milestone is the plan's tasks for that app in the phases below, one job, ending in a commit, and must pass its own hidden tests and every earlier milestone's.

| Milestone | Phases (user stories) | Python (`desktop/`) | Swift (`mobile/`) |
|---|---|---|---|
| 1 | Setup, foundation, booking, records | T001, T002, T004, T006, T008, T010, T012, T014, T016, T018, T020, T022, T024–T027, T029–T031 | T001, T003, T005, T007, T009, T011, T013, T015, T017, T019, T021, T023, T028 |
| 2 | Field time, invoicing and payment | T032, T034, T036, T037, T039, T041, T043 | T033, T035, T038, T040, T042 |
| 3 | Extensions | T044, T046 (desktop), T047, T049 | T045, T046 (mobile), T048, T051, T053 |
| 4 | Utilization and polish | T050, T052, T054–T058 (desktop) | — |

Swift has three milestones: its utilization (T051, T053) joins milestone 3, as it has no server or page to finish. The exact interfaces are in `plan/contracts/interfaces.md`.
