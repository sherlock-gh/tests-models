# Quickstart: Validation Guide

Prerequisites: Python 3.11+, Swift 5.9+ toolchain. No network or accounts needed. All data is synthetic.

## Desktop
1. `python3 desktop/seed.py --data data/desktop.json` — creates 12 synthetic cleaners and sample clients.
2. `python3 -m desktop.cleaning.server --data data/desktop.json` — serves `http://127.0.0.1:8000/`.
3. Check in the browser or with the [HTTP API](contracts/http-api.md): book jobs, view a cleaner's day, arrive/depart, extend, pay, view utilization.
4. `python3 -m unittest discover desktop/tests` — unit, conformance and stress tests.

## Mobile logic
1. `cd mobile && swift test` — unit, conformance and stress tests for `CleaningCore`.

## End-to-end scenarios to confirm
- Book 4 h × 2 cleaners on a Monday → 8:00–12:00 (C1).
- Complete a two-cleaner job (4h00m / 4h10m) → invoice $367.50; partial payment refused; full payment settles it (C10, C12).
- Extend a job so a later job moves; verify no overlaps anywhere (C13, C18).
- Submit invalid input and a missing record → visible error, data unchanged, server still responding (SC-003).

Expected: all tests pass; stress test reports zero overlaps over ≥ 1,000 operations. Scenarios are defined in [conformance-scenarios.md](contracts/conformance-scenarios.md).
