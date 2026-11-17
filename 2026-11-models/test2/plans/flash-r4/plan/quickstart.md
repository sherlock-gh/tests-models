# Quickstart: Validate the Cleaning Scheduling & Billing Feature

End-to-end validation guide for `specs/001-cleaning-scheduling-billing/spec.md`. Rules
live in data-model.md; interfaces in contracts/desktop-api.md and
contracts/mobile-logic.md. This is a run/validate guide — implementation details belong
in tasks.md.

## Prerequisites

- Python 3.14 (`python3 --version`) — desktop app, stdlib only.
- Swift 6.1 toolchain with SwiftPM (`swift --version`) — mobile logic package.
- Repo root: `/Users/sherlock/workspaces/tests/2026-11-models/round4-a/test1-flash-r1/cleaning`

## Setup

```bash
cd <repo root>
python3 -m venv .venv && .venv/bin/pip install -r desktop/requirements.txt  # pytest only
# mobile needs no install: SwiftPM resolves no external dependencies
```

Each app keeps data in its own local file (`desktop/data.json`; a caller-supplied path
for mobile). Delete those files for a clean run. The two apps are never connected
(FR-018).

## 1. Mobile logic package — full rule engine (fastest proof)

```bash
cd mobile
swift test --disable-sandbox          # this host's SwiftPM sandbox fails without the flag
```

Expected: all `Tests/CleaningLogicTests` pass, covering the golden vectors from
contracts/mobile-logic.md — booking grid + 1 h spacing (12:00→13:00, 12:10→13:15),
Saturday→Monday 8:00, 10 h = 8+2 on later workdays with first-part cleaners preferred
when free (other free cleaners otherwise), 90-day refusal with nothing created,
taps to the minute and Q5 refusals, invoice $157.50/$180.00/$337.50 on last depart,
exact-payment settlement (33700¢ refused, 33750¢ settled), extension cascade
(3×20 min → later 13:15 job re-booked ≥ 14:00), cleaner/client deletion cascades,
utilization 22:00–02:00 → 2 h + 2 h and 9 h → 540/480.

## 2. Desktop app — test suite

```bash
cd desktop
../.venv/bin/python -m pytest -q
```

Expected: pytest green across booking, taps/invoicing, cascades, CRUD errors, and
utilization modules. Note: this sandbox cannot connect to loopback HTTP ports; the suite
drives the `create_app(data_file).request(method, path, body)` interface specified
in contracts/desktop-api.md, not via curl (research R6).

## 3. Desktop app — run it for a person

```bash
cd desktop
PORT=18080 ../.venv/bin/python app.py      # serves http://127.0.0.1:$PORT (use 18080–18089)
```

Open http://127.0.0.1:18080 and walk the stories end-to-end:

1. **US5 first**: create 12 cleaners and a few clients via the page (POST /api/cleaners,
   /api/clients). Re-read the lists — records persisted.
2. **US1**: create a job (client, 2 cleaners, 10 h, next Monday). The page shows the
   system-chosen cleaners, quarter-hour start, and two parts (8 h + 2 h, each booked
   independently on later workdays, first-part cleaners if free or other free cleaners
   otherwise). Book against a busy cleaner and confirm starts honor
   ≥ 1-hour spacing. Request a Saturday job → Monday 8:00. Attempt a 90-day-blocking
   scenario (fill calendars) → refusal message, no job appears (contracts/desktop-api.md).
3. **US2**: open the day view for an assigned cleaner, tap Arrive/Depart; verify the
   recorded minutes.
4. **US3**: when the last cleaner departs, the invoice appears instantly with per-cleaner
   lines and total; record a wrong payment → message, still unsettled; the exact amount
   → settled. Try deleting that job → refused.
5. **US4**: arrive on a job, extend 20 minutes ×3; verify the cleaner's end and any
   later job re-booked ≥ 1 h after; try the 22:00→02:00 overnight job.
6. **US5 removals**: delete a cleaner with future jobs → jobs remain, re-booked with
   free cleaners; delete a client → their future jobs cancelled, arrived-at job intact.
7. **US6**: utilization view shows per-day /8 and per Mon–Sun week /40, uncapped,
   overnight split 2/2.
8. Restart `python app.py` — everything comes back from `data.json` (FR-018).

Every failure above shows an in-page message (error envelope), the app continues, and
the data file is unchanged by the failed operation (FR-019, SC-005).

## 4. Cross-app parity check

Run both suites; both must pass the identical golden vectors listed in
contracts/mobile-logic.md. The apps still hold separate files (open desktop/data.json
and the mobile data file — records were entered independently in each).

## Done means

- `swift test --disable-sandbox` green, `pytest -q` green.
- The manual walk reproduces every numbered acceptance scenario from spec.md with no
  crash and no overlap created anywhere (SC-001–SC-007).
