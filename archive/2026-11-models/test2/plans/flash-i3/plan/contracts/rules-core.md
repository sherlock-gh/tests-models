# Contract: Shared Rules Core (both apps)

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md) | **Data model**: [data-model.md](data-model.md)

Both implementations — the Python desktop app and the Swift `CleaningKit` package — MUST
satisfy the invariants and golden pins below. These are the checkpoints task-level contract
tests pin; a rule lives here once and is referenced by each app contract. All times are the
business's local time; the workday is 8:00–17:00 Monday–Friday; there are no holidays.

## Invariants

- **I1 Shadow**: for one cleaner, no two booked job parts where the second starts less than
  60 real minutes (3600 s) after the first ends. Booking, extension and rebooking preserve
  this; after any successful operation a full-store scan finds zero violations.
- **I2 Quarter hour**: every booked start is on a 15-minute boundary at/after 8:00
  (8:00, 8:15, …). Boundary pins: after an end at 12:00 the earliest next start is 13:00
  (12:45 illegal); after 12:10 it is 13:15.
- **I3 Day window**: a booked part starts and ends within 8:00–17:00 of a weekday. Sat/Sun
  requested days resolve to Monday 8:00. Extensions that push an end past 17:00 are legal
  but only via the extension flow, never via booking.
- **I4 Split**: expected length L > 8 h ⇒ parts = floor(L/8h) × 8h + (L mod 8h if ≠ 0), on
  consecutive week days, same cleaner crew on every part. An 8 h job = one part (8:00–16:00
  when unconstrained); a 10 h job = 8 h + 2 h on the next workday.
- **I5 90-day refusal**: booking search covers requested_day..requested_day+90; exhaustion
  ⇒ refusal message, store unchanged.
- **I6 Crew self-assignment**: the system assigns 1–3 cleaners itself at booking; any free
  set may be chosen (tests assert legality, not identity — except a single-cleaner job
  names the cleaner set's size).
- **I7 Invoice moment**: invoice exists iff every assigned cleaner has departed; issued in
  that same operation. Line cents = round-half-up(minutes × 4500 ÷ 60); total = Σ line
  cents. Golden: 210 min → 15750¢; 240 min → 18000¢; both cleaners on one invoice →
  33750¢.
- **I8 Settlement**: exactly one payment, cents-equal to the total, sets settled; any other
  amount (or a second payment, or unknown invoice) is refused, invoice stays as it was.
- **I9 Deletion semantics**: cleaner deletion rebooks their *future* jobs (nobody tapped
  Arrive) via the booking rule with any free cleaners and never moves jobs already arrived
  on; client deletion cancels their future jobs; a job with an issued invoice is
  undeletable; issued invoices are immutable and undeletable.
- **I10 Error discipline**: every failure (bad input, unknown record, impossible request)
  returns an error message to the caller, changes nothing in the data file, and leaves the
  app usable.

## Golden scenario pins (run these in BOTH apps)

| # | Scenario (from problem.md "Examples at the boundaries") | Expected |
|---|---|---|
| G1 | Cleaner's job ends 12:00; book same cleaner again | next start 13:00 ok; 12:45 rejected |
| G2 | Job ends 12:10 | earliest next start 13:15 |
| G3 | Job requested Saturday | starts Monday 8:00 |
| G4 | 8 h job | one part 8:00–16:00 (same day) |
| G5 | 10 h job | part 1 = 8 h workday N, part 2 = 2 h workday N+1, same crew |
| G6 | Calendar full for 90+ days | refused with message; data file unchanged |
| G7 | Arrive 9:00, Depart 12:30 | line 15750¢ ($157.50) |
| G8 | Two cleaners 210 min + 240 min | lines 15750¢ + 18000¢; total 33750¢ |
| G9 | Worked 22:00–2:00 | utilization: 2 h day 1, 2 h day 2 |
| G10 | 45 h in a Mon–Sun week | weekly report shows 45 of 40 (no cap) |
| G11 | Cleaner with arrivals arrives again | refused, nothing changes |
| G12 | Depart with no Arrive | refused, nothing changes |
| G13 | More-time before Arrive / after completion | refused, nothing changes |
| G14 | Extension leaves later job < 1 h after new end | that job rebooked ≥ new end + 1 h by booking rule; cascade until clean |
| G15 | Delete cleaner with 2 future + 1 arrived job | 2 future rebooked with free cleaners; arrived job untouched |
| G16 | Delete client with future jobs | those jobs cancelled |
| G17 | Delete job with issued invoice | refused; job and invoice unchanged |
| G18 | Pay unsettled invoice with total±1¢ | refused, remains unsettled |
| G19 | Pay exact total | settled |
| G20 | Update/delete issued invoice; pay settled invoice | refused, nothing changes |

## Naming and message conventions

- Error responses carry a human-readable message naming the refused rule (e.g. "No slot for
  this job within 90 days of the requested day."). The app surfaces it, changes nothing,
  keeps running (I10).
- "Future job" means status `booked`; "settled" derives from a matching Payment; both apps
  use these definitions in their outputs.
