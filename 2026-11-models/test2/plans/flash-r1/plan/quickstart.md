# Quickstart: Cleaning Scheduling and Billing

**Date**: 2026-11-11 | **Plan**: [plan.md](./plan.md)

Prerequisites: Python 3.11+, Swift 5.9 toolchain (`swift build`/`swift test` works on macOS; pass `--disable-sandbox` to swift if the sandbox blocks SwiftPM). All work is local and synthetic.

## Setup

```bash
# Back office (Python)
python3 -m venv .venv
.venv/bin/pip install -r webapp/requirements.txt   # flask (stdlib fallback path needs nothing)

# Cleaner logic (Swift package)
cd CleanerApp && swift build && swift test         # local, no network
```

## Run the back-office page

```bash
.venv/bin/python webapp/app.py                     # serves 127.0.0.1:$PORT (use 18080-18089)
```

Open `http://127.0.0.1:18080/`. Data persists in `webapp/data/store.json` (one file, inspectable). The Swift package keeps its own file — the two apps are intentionally **not** connected.

## Run the tests

```bash
.venv/bin/pytest tests/                            # unit + contract + scripted audit
cd CleanerApp && swift test                        # mirrored rule suites
```

Both suites must be green per [contracts/](./contracts/) (parity scenarios).

## Validation scenarios

Rule details live in [data-model.md](./data-model.md) and `shared/rule-spec.md`; routes/API shapes in [contracts/backoffice-web.md](./contracts/backoffice-web.md) and [contracts/cleaner-logic-swift.md](./contracts/cleaner-logic-swift.md). Reproduce each scenario in both apps (via pages, or via the Swift `Store` API in tests) and run the audit assertion group (4 invariants) after each.

| # | Scenario (spec ref) | Steps | Expected |
|---|---|---|---|
| V1 | US1-AC1 earliest slot | Create 3 cleaners + client; book 3-cleaner, 4 h, next Monday | Job on earliest workday ≥ that Mon, 8:00 start, 3 distinct cleaners, inside 8:00–17:00 |
| V2 | US1-AC2 spacing | Cleaner booked 8:00–12:00 Tue; book 1-cleaner Tue | A *free* cleaner chosen; audit: gap ≥ 1 h everywhere |
| V3 | US1-AC3 too long | Book 9.5 h job | Refused with message; store byte-identical (FR-002) |
| V4 | US1-AC4 CRUD | Read/update/delete cleaner, client, job incl. missing id + bad input | Changes visible on read; errors shown, app alive (FR-001/016) |
| V5 | US2 taps | Assign 2 jobs today; Arrive 8:05, Depart 12:05 | worked 4.0 h; day view matches booking (FR-006/007) |
| V6 | US2-AC3 double Depart | Depart again | Error, nothing changes |
| V7 | US3-AC1 invoice | 2-cleaner job, A 4.0 h, B 3.5 h, last Depart | Invoice at that moment: $180.00 + $157.50 = $337.50 (FR-011/012) |
| V8 | US3-AC2 settlement | Pay $337.50 → settled; pay $337.49 first | mismatch refused unsettled; equal settles (FR-013/014) |
| V9 | US3-AC3 half-done | 1 of 2 cleaners departed | No invoice yet |
| V10 | US4-AC1 extension cascade | Job ends 12:00, later job 12:30 same cleaner; extend ×1 | New end 12:20; later job rebooked ≥ 13:20 per booking rule (FR-009) |
| V11 | US4 chain | Extend repeatedly until no later job violates spacing | Chain terminates; audit clean (SC-004) |
| V12 | US4-AC3 delete cleaner w/ jobs | Delete cleaner holding future 2-cleaner job while <2 cleaners remain | Reported, **nothing changes**; otherwise rebooked per rule (FR-010) |
| V13 | US4-AC4 delete client w/ invoice | Future jobs + issued invoice; delete client | Future jobs cancelled; invoice identical before/after |
| V14 | Weekend request | Book for Saturday | Lands from following Monday ≥ 8:00 (edge case) |
| V15 | Same-instant taps | Arrive and Depart at the same minute | Allowed; that line $0.00 (edge case) |
| V16 | Extension past 17:00 | Extend a job ending 16:50 | End 17:10 allowed; bumped rebookings still inside window (FR-008) |
| V17 | Pay settled / unknown | Pay an already-settled invoice; pay id 99999 | Refused, no change, messages shown (FR-016) |
| V18 | SC-001 audit workload | Scripted: 12 cleaners, 2 staff role ops, ~4.14 h ± 1.75 h job mix | Zero failures; audit invariants hold (tests/audit/) |
| V19 | Utilization | Worked times in a week; GET /utilization?day=… | Day/week totals = Σ worked vs 8 h / 40 h (FR-015) |
| V20 | Swift parity | Replay V1–V17 through `Store` in XCTest | Same results/errors as Python side |

**Pass criteria**: every scenario matches its Expected column, the 4 cross-entity invariants from [data-model.md](./data-model.md) hold after every mutating scenario, and error scenarios leave the store unchanged.
