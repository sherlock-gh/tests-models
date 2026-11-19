# Implementation Plan: Cleaning Business Scheduling and Billing

**Branch**: `001-cleaning-scheduling-billing` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-cleaning-scheduling-billing/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Two independent apps that enforce identical scheduling and billing rules for a fictitious
house-cleaning business (12 cleaners, 2 back-office staff), each keeping its data in its own
local file, with no connection between them:

1. **Desktop back office** — a local web page served by Python (stdlib `http.server`
   WSGI-style app, no third-party frameworks).
2. **Mobile cleaner logic** — a Swift package with no UI, exposing the field operations
   (day list, Arrive, Depart, more-time) as testable API functions.

Core engine (shared rules, duplicated per app in Python and Swift): CRUD for cleaners,
clients and jobs; self-booking into the earliest quarter-hour slot on or after the
requested day within a 90-day search; 8:00–17:00 Mon–Fri workday with 1-hour shadow
(overlap = second start < 1 h after first end); >8 h jobs split into 8-hour parts plus the
rest on consecutive workdays with the same crew; Arrive/Depart taps to the minute; 20-minute
extensions with cascading rebooking; instant invoice issue at last departure ($45/h per
cleaner line, rounded to the nearest cent half-up, total = sum of lines = e.g. 15750 cents
for 3 h 30 min); one-shot full-total settlement; per-cleaner utilization out of 8 h/day and
40 h/ Mon–Sun week with midnight splitting. Every error shows a message, changes nothing,
and leaves the app running.

## Technical Context

**Language/Version**: Python 3.12+ (3.14 verified on this host) for the desktop app; Swift 6.1 (6.1.2 verified on this host) for the mobile logic package

**Primary Dependencies**: Python standard library only — `http.server`/`wsgiref` for serving, `json` for persistence, `decimal` for half-up cent rounding, `zoneinfo` for local time and clock changes, `unittest` for tests. Swift: Foundation only (`Foundation.Calendar`/`Date` for quarter-hour, workday and DST math), `XCTest` for tests. No third-party packages in either app.

**Storage**: One local JSON data file per app (desktop: `desktop/data.json`; mobile: a file URL supplied by the caller). No shared storage; the two files are independent. Whole-file atomic rewrite (write temp + rename) after each successful operation.

**Testing**: `pytest` (or `python -m unittest`) for the Python app; `swift test` (XCTest) for the Swift package. Golden boundary cases from problem.md are encoded as contract tests in both apps (see `contracts/`).

**Target Platform**: Desktop app runs on this macOS host and serves `127.0.0.1` (port from `$PORT`, default 18080) for a local browser. Swift package builds and tests on macOS via SwiftPM (`swift build` / `swift test`, built with `--disable-sandbox` on this host).

**Project Type**: Twin apps — one local web app (Python-served page), one UI-less logic library (Swift package). Same rules, two implementations, no sync.

**Performance Goals**: Single business, tiny scale: booking searches (≤90 days × quarter-hour grid × 12 cleaners) resolve in well under 1 second; UI interactions are local and instantaneous. No throughput targets.

**Constraints**: No network services, accounts or outside data; all data synthetic. No enforcement beyond the written rules (FR-017). Money in integer cents with `Decimal` half-up rounding (never binary floats). Times are the business's local time with the calendar's clock changes applied; no holidays.

**Scale/Scope**: 12 cleaners, 2 back-office staff, hundreds of jobs per app. Two source trees (`desktop/`, `CleaningKit/`), roughly 1.5–2.5 k lines total including tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution file exists at `.specify/memory/constitution.md`; there are no project
constitution gates. The gate was therefore evaluated against the two hard constraints
written into the problem statement itself:

- **No rules beyond the spec** (FR-017, "No other rules"): PASS — every rule in
  research.md traces to a problem.md/spec.md sentence; invented rules (lead-time notice,
  due dates, max extensions) are explicitly rejected.
- **Errors never crash, never half-change, never stop the app** (FR-016): PASS — designs
  use validate-then-mutate order with whole-file atomic persistence and error values, not
  exceptions escaping request handlers.

Post-design re-check (after Phase 0/1, 2026-11-13): PASS — research.md, data-model.md,
contracts/ and quickstart.md introduce no additional rules and no third-party
dependencies. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-cleaning-scheduling-billing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── rules-core.md            # shared rule invariants both apps must satisfy
│   ├── desktop-api.md           # HTTP endpoints of the Python app
│   └── cleaner-api.md           # Swift package public API
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
desktop/                         # Python back-office app (web page + server)
├── app.py                       # WSGI app + request routing, error envelope (FR-016)
├── server.py                    # `python -m desktop.server` → http.server on $PORT
├── static/index.html            # back-office page (vanilla JS, fetch → app.py routes)
├── store.py                     # JSON file load/save, atomic rewrite, id assignment
├── models.py                    # Cleaner, Client, Job, JobPart, Tap, Invoice, Payment
├── timeutil.py                  # quarter-hour grid, workdays, shadow, DST (zoneinfo)
├── booking.py                   # earliest-slot search, >8 h split, cascade rebook
├── billing.py                   # Decimal cent math, invoice issue, settlement
├── utilization.py               # per-day / per-week billable hours, midnight split
└── tests/
    ├── test_booking.py          # US1 boundaries (13:00/13:15, Saturday, 8 h/10 h, 90 d)
    ├── test_taps_billing.py     # US2 (taps to the minute, 15750/18000/33750 cents)
    ├── test_extensions.py       # US3 (20-min steps, shadow cascade, past 17:00)
    ├── test_records.py          # US4 CRUD + deletion/rebooking/cancellation
    ├── test_settlement.py       # US5 (full-total only, settled/unsettled)
    └── test_utilization.py      # US6 (22:00–2:00 → 2 h + 2 h, uncapped totals)

CleaningKit/                     # Swift package: cleaner-side logic, no UI
├── Package.swift
├── Sources/CleaningKit/
│   ├── Models.swift             # mirrors desktop/models.py
│   ├── TimeUtil.swift           # quarter-hour grid, workdays, shadow (Foundation)
│   ├── Store.swift              # JSON file persistence at a caller-supplied URL
│   ├── Booking.swift            # earliest-slot search, split, cascade rebook
│   ├── Billing.swift            # cent rounding via Decimal/round(.down) analogue
│   ├── DayOps.swift             # day list, Arrive, Depart, more-time
│   └── Utilization.swift        # per-day / per-week billable hours
└── Tests/CleaningKitTests/
    ├── BookingTests.swift
    ├── TapAndInvoiceTests.swift
    ├── ExtensionTests.swift
    ├── RecordsTests.swift
    ├── SettlementTests.swift
    └── UtilizationTests.swift

Procfile                         # demo server: `web:` line serving desktop app on $PORT
```

**Structure Decision**: Two sibling top-level projects, one per app, exactly as the problem
statement demands ("two apps that follow the same rules, each keeping its data in its own
local file; the two are not connected"). `desktop/` is the Python web app (server +
static page + rule modules); `CleaningKit/` is a plain SwiftPM library with an XCTest test
target. Rules are duplicated, deliberately, in both languages rather than shared — the
contract documents in `contracts/` are the single source of truth that both implementations
are tested against.

## Complexity Tracking

> No constitution violations to justify; both gates pass. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)      |            |                                     |

## Verification Sweep (post-generation checks)

- [x] `plan.md` matches the plan-template shape (Summary, Technical Context with the
      Phase 0 Resolve section, Project Structure, Phase 0/1 outputs, Complexity Tracking);
      Constitution Check filled with no unjustified violations.
- [x] `research.md`: R1–R12, each with Decision / Rationale / Alternatives considered;
      every NEEDS CLARIFICATION from Technical Context removed (grep = 0).
- [x] `data-model.md`: all entities (Cleaner, Client, Job, JobPart, Tap, Invoice,
      InvoiceLine, Payment, UtilizationReport), fields, rules, relationships, Job state
      machine, validation summary.
- [x] `contracts/`: rules-core.md (invariants I1–I10 + golden pins G1–G20),
      desktop-api.md, cleaner-api.md — the deliverable surface for `/speckit-tasks`.
- [x] `quickstart.md`: prerequisites, run/test commands, validation walk-throughs mapped
      to golden pins; no implementation code.
- [x] Every decision problem.md doesn't settle is Q1–Q7 in `questions.md` with the
      assumed answer; the affected research sections cite the question.
- [x] Stdlib-only claims re-checked on this host (Python 3.14.7 with `http.server`,
      `decimal`, `zoneinfo`, `fractions`; Swift 6.1.2 toolchain works with
      `swift build/test --disable-sandbox`).
- [x] Independent-app constraint (separate files, no sync) and billing consistency
      (4500 cents/h, half-up, total = sum of lines) re-checked across plan, research,
      data-model and all three contracts.
If `/speckit-analyze` or the tasks phase disagrees with an assumed answer here, amend that
answer in `questions.md` first — never change rule wording silently, and never weaken a
check to make an artifact pass.

Next steps belong to the workflow owner: `python -m pytest desktop/tests -q` and
`(cd CleaningKit && swift test --disable-sandbox)` after implementation; task generation
via `/speckit-tasks` — not yet run from this plan.
