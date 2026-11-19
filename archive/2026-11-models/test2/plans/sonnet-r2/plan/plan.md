# Implementation Plan: Scheduling and Billing for a House-Cleaning Business

**Branch**: `001-cleaning-scheduling-billing` (no branch created; work stays on `main`) | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-cleaning-scheduling-billing/spec.md`

## Summary

Two expressions of one rule set: a desktop back-office app (local web page served by Python) and a mobile logic layer for cleaners (Swift package, no UI). Both implement the same booking, overlap, extension, time, invoicing, settlement and utilization rules, each over its own local JSON file, with no network services. Because the rules are duplicated across two languages, a shared set of language-neutral conformance scenarios (`contracts/conformance-scenarios.md`) is run against both implementations to keep them in agreement. See [research.md](research.md) for decisions.

## Technical Context

**Language/Version**: Python 3.11+ (desktop); Swift 5.9+ (mobile logic package)

**Primary Dependencies**: None beyond the standard libraries (Python `http.server`, `json`, `datetime`, `unittest`; Swift Foundation, XCTest). No network services or third-party packages.

**Storage**: One local JSON file per app, written atomically (temp file + rename) after every successful change; no database.

**Testing**: `unittest` (Python); XCTest via `swift test` (Swift); shared conformance scenarios implemented in both; a seeded randomized stress test (≥1,000 operations) asserting zero overlaps/double bookings (SC-002).

**Target Platform**: Desktop: any OS running Python, browser on localhost only. Mobile: iOS 16+/macOS 13+ Swift package (library only).

**Project Type**: Desktop web app (local server + page) plus a UI-less Swift library.

**Performance Goals**: Booking/re-booking for 14 users and a few thousand jobs completes in well under 1 s; no special optimization.

**Constraints**: Offline; localhost-bound server; every failure returns a visible error, leaves data unchanged and does not crash (FR-020); integer arithmetic for time (minutes) and money (cents); all data synthetic.

**Scale/Scope**: 12 cleaners, 2 back-office staff, jobs of 1–3 cleaners averaging ~4.14 h (σ ≈ 1.75 h).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution exists (`.specify/memory/constitution.md` is absent), so there are no project-specific gates. Applying the spec's own principles as checks:

- Offline, no network services, no accounts: PASS (localhost only, local file).
- Same rules in both expressions: PASS (shared conformance scenarios).
- Errors never crash or change data: PASS (validate-then-commit, all-or-nothing operations; see data-model.md).
- Synthetic data only: PASS (seed script generates fake data).

Post-design re-check: PASS, no violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-cleaning-scheduling-billing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── operations.md              # shared operation/rule contract (both apps)
│   ├── http-api.md                # desktop local HTTP/JSON API
│   └── conformance-scenarios.md   # language-neutral scenarios both suites run
└── tasks.md                       # produced later by /speckit-tasks
```

### Source Code (repository root)

```text
desktop/
├── cleaning/
│   ├── rules.py        # scheduling, overlap, extension, billing, utilization (pure)
│   ├── store.py        # JSON file load/save, atomic write
│   ├── service.py      # operations: CRUD, book, arrive/depart, extend, pay
│   ├── server.py       # http.server JSON API + static page
│   └── static/         # index.html, app.js, style.css
├── seed.py             # synthetic data generator
└── tests/              # unit, conformance, stress

mobile/
├── Package.swift
├── Sources/CleaningCore/   # Rules, Models, Store, Service (no UI)
└── Tests/CleaningCoreTests/ # unit, conformance, stress
```

**Structure Decision**: Two sibling top-level projects (`desktop/`, `mobile/`) that share no code, only the contracts and conformance scenarios, matching the spec's "two expressions of one solution".

## Complexity Tracking

No constitution violations; nothing to justify.
