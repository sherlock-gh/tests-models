# Quickstart: Cleaning Business Scheduling and Billing

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md)

Validation guide for the two apps. Rule details live in
[contracts/rules-core.md](contracts/rules-core.md); field shapes in
[data-model.md](data-model.md), [contracts/desktop-api.md](contracts/desktop-api.md) and
[contracts/cleaner-api.md](contracts/cleaner-api.md). Nothing here is implementation code.

## Prerequisites

- macOS host (this one), Python 3.12+ and Swift 6.1+ on `PATH` (verified: 3.14.7 / 6.1.2).
- No installs: Python stdlib and Foundation only (research R1). No network services needed.
- All data is synthetic; the fictitious business has 12 cleaners and 2 back-office staff.

## 1. Desktop back-office app

```bash
cd desktop
python -m desktop.server          # serves http://127.0.0.1:${PORT:-18080}
```

Open the page in a browser. Data file: `desktop/data.json` (auto-created; override with
`CLEANING_DATA=/path/to/file.json`).

Validation walkthrough (page forms — each expected result is a rules-core golden pin):

1. Create 12 cleaners ("Ana"…, 2 clients ("Acme Household", "Blue house")).
2. Book a 2-cleaner job, requested Tue 2026-11-17, 3 h → appears at the earliest
   quarter-hour slot ≥ Tue 8:00, two cleaners assigned (G1–G3 family).
3. Book a 10-hour job → two parts, 8 h + 2 h, consecutive workdays, same crew (G5).
4. Fill the calendar for 91 days, then book → refusal message
   "No slot for this job within 90 days...", and refreshing shows nothing changed (G6).
5. Tap Arrive/Depart buttons for both cleaners of a job → after the last Depart the job
   page shows an issued invoice with each line's minutes and cents (G7/G8 family).
6. Pay the exact total → moves to the Settled group; pay total−1¢ → refused (G18/G19).
7. Try delete on an invoiced job and edit on an invoice → refused with a message (G17/G20).
8. Utilization page: daily/weekly per cleaner; a cleaner who worked nothing shows 0 h (G9
   spans arrive overnight via more-time, G10 for the 45 h week is exercised by tests).

## 2. Mobile logic package (Swift, no UI)

```bash
cd CleaningKit
swift build --disable-sandbox
swift test  --disable-sandbox
```

(`--disable-sandbox` is required on this host — SwiftPM's nested sandbox is denied;
research R1.)

The XCTest suite is the validation: `BookingTests`, `TapAndInvoiceTests`, `ExtensionTests`,
`RecordsTests`, `SettlementTests`, `UtilizationTests` pin every golden scenario G1–G20 of
[contracts/rules-core.md](contracts/rules-core.md) through the public API of
[contracts/cleaner-api.md](contracts/cleaner-api.md), each test using its own temp
store file (the two apps' files never touch, research R8).

## 3. Rule engine tests (desktop)

```bash
cd <repo root>
.venv/bin/python -m pytest desktop/tests -q      # or: python -m pytest desktop/tests -q
```

Expected: all green — `test_booking.py` (US1: 13:00-vs-12:45, 13:15, Saturday→Monday 8:00,
8 h/10 h split, 90-day refusal), `test_taps_billing.py` (15750/18000/33750 cents),
`test_extensions.py` (cascade + past-17:00), `test_records.py` (CRUD + rebook/cancel),
`test_settlement.py`, `test_utilization.py` (22:00–2:00 → 2 h + 2 h, 45-of-40).

## 4. Error discipline spot checks (SC-003)

With either app running: send bad input (cleaners_needed = 5), reference a missing record
(job 99999), and provoke an impossible request (pay a settled invoice). Each must show an
error, leave the data file unchanged, and keep the app responding. For the desktop app:

```bash
curl -s -X POST localhost:18080/api/jobs -d '{"client_id":1,"cleaners_needed":5,
"expected_length_min":180,"requested_day":"2026-11-17"}'   # -> {"error": ...}, file unchanged
```

## Definition of done for this feature

Every acceptance scenario in [spec.md](spec.md) User Stories 1–6 passes in both apps, the
goldens G–I table holds, and neither app crashes or mutates the data file on any error
(re-check gates in [plan.md](plan.md) Constitution Check section).
