# Implementation Plan: Cleaning Business Scheduling and Billing

**Branch**: `001-cleaning-scheduling-billing` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-cleaning-scheduling-billing/spec.md`

## Summary

Two disconnected apps enforce identical scheduling/billing rules for a house-cleaning
business, each persisting to its own local file: a back-office desktop app (a local web
page served by Python) and a cleaners' mobile app provided as a Swift logic package with
no UI. The core engine is a deterministic booking rule — earliest quarter-hour slot on or
after the requested day inside the 8:00–17:00 Mon–Fri workday where enough cleaners are
free, with a ≥1-hour spacing rule, 8-hour multi-day splits, and a 90-day search horizon —
shared in spirit by both apps and exercised by the same rule-set tests (golden examples:
3 h 30 min → $157.50; 2+2 overnight split; Saturday request → Monday 8:00). Each app is
a single local project with a pure domain core, an atomic JSON-file store, and a thin
delivery shell; all error paths are non-crashing, message-returning, all-or-nothing.

## Technical Context

**Language/Version**: Python 3.14 (installed; stdlib only — no third-party packages) and
Swift 6.1.2 / SwiftPM (installed)

**Primary Dependencies**: None beyond stdlib: Python `http.server` + `json` + `decimal` +
`zoneinfo`; Swift Foundation (`Date`, `Calendar`, `TimeZone`). The mobile package is
explicitly UI-free — no SwiftUI/UIKit.

**Storage**: One JSON data file per app, on the same machine, never shared or connected
(FR-018). Writes are atomic (write temp file + rename) and each operation either fully
applies or fully fails.

**Testing**: Desktop — `pytest` run via terminal (the execute_code kernel's python lacks
pytest). Mobile — `swift test` (XCTest via SwiftPM), always with `--disable-sandbox`,
which this host requires for SwiftPM builds.

**Target Platform**: Back-office machine (macOS today; any platform with the Python
stdlib qualifies) running a loopback web server; mobile logic compiles and tests as a
SwiftPM package for macOS (logic-first, iOS-ready types only).

**Project Type**: Two independent local apps in one repo (web app + logic package).

**Performance Goals**: Small business scale — booking search (≤90 days × 36 quarter-hours
× ≤12 cleaners) returns in well under a second; interactive request/response feels
instant. No throughput targets.

**Constraints**: Offline-only, no network services, no accounts (FR-020); money math in
Decimal cents; all times in the business local timezone `America/Los_Angeles` with
DST observed (FR-007); every operation atomic at the file level.

**Scale/Scope**: 12 cleaners, 2 back-office staff, ~4.14 h average job (σ ~1.75 h);
6 entities, 2 apps, ~15–20 source modules, thousands of simulated bookings for
SC-002-style sweeps.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: PASS — `.specify/memory/constitution.md` does not exist in this repo, so no
project constitution is in force. The gate is therefore evaluated against the spec's own
hard rules (FR-020 "no other rules", FR-018 two disconnected apps, FR-019 non-crashing
errors): the plan adds no extra domains, fields, services, or rules beyond spec +
questions.md assumptions, keeps the apps disconnected, and gives every error path a
message and no-change semantics. No violations to justify → Complexity Tracking stays
empty. (Re-checked after Phase 1 — see Post-Design Re-check at the bottom of
research.md.)

## Project Structure

### Documentation (this feature)

```text
specs/001-cleaning-scheduling-billing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── desktop-api.md   # HTTP endpoint contract for the web app
│   └── mobile-logic.md  # Swift package public API contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
desktop/                     # Back-office app: Python web page + engine (own file, own data)
├── app.py                   # stdlib http.server entry point (loopback, 127.0.0.1)
├── static/index.html        # single-page back-office UI (vanilla JS, same-origin fetch)
├── cleaning/                # pure domain package (no I/O except the store)
│   ├── models.py            # Cleaner, Client, Job, JobPart, Assignment, Invoice, Payment
│   ├── store.py             # atomic JSON file store (load/modify/save, fsync+rename)
│   ├── scheduling.py        # booking rule, splits, overlap check, re-book cascades
│   ├── timezone_util.py     # America/Los_Angeles quarter-hour grid + DST helpers
│   ├── invoices.py          # completion detection, $45/h Decimal lines, settlement
│   ├── utilization.py       # per cleaner per day (of 8) / Mon–Sun week (of 40)
│   └── errors.py            # AppError(message) raised, caught, never crashes
└── tests/                   # pytest: booking, taps, invoices, cascades, utilization

mobile/                      # Cleaners' app logic: Swift package, no UI (own file, own data)
├── Package.swift
├── Sources/CleaningLogic/
│   ├── Models.swift         # same entities as desktop/cleaning/models.py
│   ├── Store.swift          # atomic JSON file store (Data write + replace)
│   ├── Scheduling.swift     # mirror of desktop booking rule + cascades
│   ├── TimeUtil.swift       # TimeZone-aware quarter-hour grid + DST helpers
│   ├── Invoices.swift       # mirror of desktop invoice/settlement rules
│   ├── Utilization.swift    # mirror of desktop utilization
│   └── AppError.swift       # typed throwing errors, shown to the caller
└── Tests/CleaningLogicTests/
    ├── SchedulingTests.swift
    ├── TapTests.swift
    ├── InvoiceTests.swift
    ├── CascadeTests.swift
    └── UtilizationTests.swift
```

**Structure Decision**: Two sibling projects, one per app, mirroring FR-018's two
disconnected apps: `desktop/` (Python web app with its own `data.json`) and `mobile/`
(SwiftPM logic package with its own JSON file). Each app's business rules live in a pure
domain module layer (no HTTP/SwiftUI in it) with the delivery shell (HTTP server entry /
public Swift API) as a thin frontend. Synchronous request/response only — the apps never
talk to each other. Rules are duplicated deliberately: keeping one canonical Python
engine would couple the apps that must stay independent.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — the table is not in use for this plan.
