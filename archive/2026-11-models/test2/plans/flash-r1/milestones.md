# Test 2 on Flash-Next's plan (run 1, the best local plan): milestones

Every model builds from this plan (`plan/`, as `specs/001-cleaning-scheduling-billing/`), one app a build: Python builds `webapp/`, Swift builds `CleanerApp/`. A milestone is the plan's tasks for that app in the phases below, one job, ending in a commit, and must pass its own hidden tests and every earlier milestone's. The exact interfaces are in `plan/contracts/exact-interfaces.md`.

| Milestone | Phases (user stories) | Python (`webapp/`) | Swift (`CleanerApp/`) |
|---|---|---|---|
| 1 | Setup, foundation, booking and records | T001, T002, T004–T008, T012–T016, T018, T019 | T001, T003, T009–T011, T017, T020 |
| 2 | Field taps, invoices and settlement | T021, T022, T024, T025, T027, T028, T030, T031 | T023, T026, T029, T032 |
| 3 | Extensions and removals | T033–T035, T037, T038 | T036, T039 (extensions, removals), T042, T044 (utilization), T046, T048 |
| 4 | Utilization and polish | T040, T041, T043, T045, T047, T049, T050 | — |

Swift has three milestones: its utilization and polish join milestone 3, as it has no pages.
