# Implementation Plan: Cleaning Scheduling and Billing

**Branch**: `001-cleaning-scheduling-billing` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-cleaning-scheduling-billing/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Scheduling, field time-tracking and billing for a 12-cleaner house-cleaning business. Back office books conflict-free jobs into the earliest feasible slot (8:00–17:00 Mon–Fri, 1 h minimum spacing per cleaner); cleaners tap Arrive/Depart; an invoice is issued automatically the moment the last cleaner departs at $45/h per cleaner's worked time; 20-minute extensions cascade rebookings; deletions rebook or cancel future jobs; utilization reports worked hours against 8 h/day and 40 h/week.

Delivered as **two expressions of one solution** (per the problem statement's known limits): a Python-served local web page for the back office, and a logic-only Swift package for cleaners with no UI. Both implement the same rules against their own local file; the two are not connected.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+ (back office web app); Swift 5.9+ (cleaner logic package)

**Primary Dependencies**: Python — Flask (or stdlib `wsgiref` fallback) for serving, stdlib only otherwise, no external services. Swift — Foundation only, no third-party packages. Shared rule logic is ported, not shared as code (the two apps are intentionally unconnected).

**Storage**: Local JSON files, one per app (atomic write: temp file + rename). No database, no network services.

**Testing**: pytest (Python side), XCTest (Swift side), plus a scripted audit workload exercising SC-001…SC-007.

**Target Platform**: Local machine — back office serves a web page on 127.0.0.1 (port 18080–18089 during validation); Swift package builds and tests on macOS.

**Project Type**: Dual — local web app (back office) + logic-only Swift package (cleaner). Single repo, two packages side by side.

**Performance Goals**: None beyond responsiveness for a 12-cleaner / 2-staff workload; booking search scans at most a bounded horizon of workdays (52 weeks), which is instant at this scale.

**Constraints**: No network services, accounts, or outside data; every error shows a message, changes nothing, and the app carries on (FR-016); times are local and minute-granular; invoices immutable once issued.

**Scale/Scope**: 12 cleaners, 2 back-office staff, 1 client base of households, steady-state booking of ~4.14 h ± 1.75 h jobs; ~1500–3000 lines total across both packages plus tests and docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` does not exist in this repository and no `.specify/extensions.yml` is present. **No constitution gates are defined**, so the gate passes vacuously. In place of constitution gates, the plan is checked against the problem statement's hard rules, which function as the project's non-negotiables:

- [x] Same rules in both expressions (booking, spacing, extending, invoicing) — gate kept via a shared rule statement referenced by both packages.
- [x] No services, no connection between the two apps, local files only.
- [x] Nothing beyond scheduling/time-tracking/billing (no payroll, recurring, maps, travel, notifications, sign-in, email, payment processing).
- [x] Synthetic data only.

**Post-Phase-1 re-check (2026-11-11, after research.md, data-model.md, contracts/, quickstart.md)**: PASS. The design adds no dependencies, no services, no synced-store abstraction, and no UI for the Swift side. The shared-rule reference file and dual test suites were evaluated against simpler alternatives and kept because they are the only defensible guard against rule drift (see research.md Decision D-1 and Complexity Tracking). No unjustified violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-cleaning-scheduling-billing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
webapp/                       # Back office: Python-served local web page
├── app.py                    # Server entry point (serves on 127.0.0.1, $PORT)
├── cleaning/
│   ├── __init__.py
│   ├── rules.py              # Canonical rules: window, spacing, booking, extension,
│   │                         # rebooking chain, invoice math, settlement (pure fns)
│   ├── models.py             # Cleaner, Client, Job, Invoice records + validation
│   ├── store.py              # JSON file persistence (atomic write), error results
│   └── views.py              # Route/page handlers: CRUD, day view, taps, invoices,
│                             # utilization; renders templates, never raises to user
├── templates/                # Jinja/html pages: back office dashboard forms and
│                             # the cleaner day page rendered with the back office DB
└── data/                     # Local JSON store (gitignored content)

CleanerApp/                   # Mobile expression: logic-only Swift package, no UI
├── Package.swift
├── Sources/CleaningLogic/
│   ├── Rules.swift           # Mirror of rules.py (same rule statement)
│   ├── Models.swift          # Cleaner, Client, Job, Invoice structs
│   └── Store.swift           # Local JSON file store
└── Tests/CleaningLogicTests/ # XCTest suites mirroring the pytest rule tests

shared/
└── rule-spec.md              # Language-neutral statement of every rule; both
                              # packages cite it; kept in-repo, not published

tests/
├── unit/                     # pytest: rules, models, store, invoice math
├── contract/                 # pytest: page/form contracts, error envelopes
└── audit/                    # scripted workload (12 cleaners, job mix
                              # 4.14±1.75 h) asserting SC-001..SC-007
```

**Structure Decision**: Two packages side by side (`webapp/` Python, `CleanerApp/` Swift), plus `shared/rule-spec.md` as the single language-neutral rule statement both must satisfy, and a top-level `tests/` tree for the Python side (Swift tests live inside their package, per SwiftPM convention). No API layer: the two apps are deliberately unconnected; parity is enforced by parallel rule tests against `shared/rule-spec.md`, not by shared runtime code.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Two items considered and recorded for transparency:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) `shared/rule-spec.md` is an extra file, not a 3rd project | Prevents rule drift between the two mandated expressions | Free-floating duplicate prose in each package drifts silently and breaks SC parity checks |
| (none) dual test suites | Problem statement mandates two independent expressions; untestable logic can't satisfy SC-002/SC-003/SC-004 | Testing only one side leaves the Swift rules unverified |
