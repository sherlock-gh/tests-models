# Implementation Plan: Cleaning Scheduling and Billing

**Branch**: `main` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

## Summary

Build two independent local implementations of scheduling, work recording and billing: a Python-served back-office web page and a Swift package exposing cleaner app logic. Each maintains its own local file and enforces the same atomic business rules. Book the earliest eligible interval, cascade rebookings after extensions and removals, snapshot invoices on completion, and accept only full payment.

## Technical Context

**Language/Version**: Python 3.11+ and Swift 5.9+ (Python 3.14 and Swift 6.1 available locally); use portable language features where possible.
**Primary Dependencies**: Python standard library and Swift Foundation/Swift Package Manager; no external services.
**Storage**: Separate local JSON files, replaced atomically after successful operations.
**Testing**: Python `unittest` and Swift XCTest via `swift test`; shared behavioral scenarios in both suites.
**Target Platform**: Local desktop browser with Python server; Swift package for mobile app integration.
**Project Type**: Local web application and independent mobile logic library.
**Performance Goals**: Correct earliest booking and responsive local use for approximately 12 cleaners and two office staff; no numerical latency requirement is specified.
**Constraints**: No external services or synchronization; synthetic data; atomic failure; weekday 08:00–17:00 normal bookings, one-hour separation and 20-minute extensions.
**Scale/Scope**: One business, variable cleaner roster, two independently persisted expressions; no authentication or payment processing.

## Constitution Check

**Pre-research**: `.specify/memory/constitution.md` does not exist, and no constitution is present in the repository. No constitutional gates can be evaluated; this is an explicit limitation, not a claim of compliance. The spec's local-only and atomicity constraints guide the design.

**Post-design**: The proposed independent local stores, transactional changes and preserved invoice snapshots support the stated feature constraints. Constitutional compliance remains unassessable until a constitution exists; no known spec conflict is introduced.

## Project Structure

### Documentation

```text
specs/001-cleaning-scheduling-billing/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/
└── quickstart.md
```

### Source Code (planned)

```text
backoffice/
├── server.py
├── cleaning/              # domain, persistence and scheduling
├── static/                # local browser interface
└── tests/
mobile/
├── Package.swift
├── Sources/CleaningLogic/
└── Tests/CleaningLogicTests/
```

**Structure Decision**: Keep the Python application and Swift package separate to meet the independent-expression requirement. Both implement the same documented contracts and acceptance scenarios, with no shared runtime or data synchronization. Storage paths should be configurable for isolated tests.

## Complexity Tracking

No known constitutional violations can be assessed in the absence of a constitution. Two implementations are required by the problem statement.
