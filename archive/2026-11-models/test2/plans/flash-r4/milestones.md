# Flash-r4 milestones

Each app is built independently from `plan/`, following the plan's phase order. Each milestone is one model job ending in a commit and includes all earlier work in that app. Python builds `desktop/`; Swift builds `mobile/` (SwiftPM target `CleaningLogic`). Refer to `plan/contracts/` for interfaces and `plan/tasks.md` for task details. Shared setup/cross-cutting tasks are assigned to both apps; each model implements and validates its own track, not a connection between the apps.

| Milestone | Plan phases | Python (`desktop/`) tasks | Swift (`mobile/`) tasks |
|---|---|---|---|
| 1 | 1–3: setup, foundation, booking (US1) | T001, T003, T004, T006, T008, T010, T012, T013, T014, T015, T016, T017, T021 | T002, T003, T005, T007, T009, T011, T012, T018, T019, T020 |
| 2 | 4–5: taps (US2), invoices and settlement (US3) | T022, T024, T025, T026, T028, T030, T031 | T023, T027, T029, T032 |
| 3 | 6: more time and rebooking cascades (US4) | T033, T035, T036 | T034, T037 |
| 4 | 7: CRUD and safe removals (US5) | T038, T040, T041 | T039, T042 |
| 5 | 8–9: utilization (US6), polish and validation | T043, T045, T046, T048, T049, T050, T051, T052, T053, T054 | T044, T047, T049, T050, T053, T054 |

T003 scaffolds both project directory trees; either app's model needs its own tree and may create the empty counterpart named in the task. T012 has a Python import gate and a Swift compile gate; each model verifies its own gate. T049 and T050 explicitly include tests for each app. T053's parity vectors are exercised independently by each app against its own store; T054's README/testing note applies to each suite. T052 is a desktop page walk only. Shared-task duplication does not imply shared runtime data or require the other app's completed implementation.
