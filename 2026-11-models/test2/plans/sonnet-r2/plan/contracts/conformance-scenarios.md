# Contract: Conformance scenarios (run by both test suites)

Each scenario starts from stated data and must produce identical results in Python and Swift. Dates: Monday = 2026-11-16.

| # | Setup | Action | Expected |
|---|---|---|---|
| C1 | 12 cleaners, no jobs | book 4 h, 2 cleaners, Mon | Mon 8:00–12:00, cleaners 1,2 |
| C2 | cleaner 1 job ends 12:00 | book job needing cleaner 1 only (1 cleaner, others busy) | starts 13:00 |
| C3 | all busy Mon | book | earliest later slot, weekends skipped |
| C4 | any | length 9 h → 8:00–17:00; 9 h 1 min refused | as stated, no change on refusal |
| C5 | any | requested Saturday | Monday |
| C6 | any | cleanersNeeded 0 or 4; cleanersNeeded 13 with 12 cleaners | `invalid_input` / `unschedulable` |
| C7 | cleaner with 2 future jobs | delete cleaner | jobs re-booked, no overlaps |
| C8 | client with future jobs + issued invoice | delete client | jobs cancelled, invoice unchanged |
| C9 | job booked | depart before arrive; arrive twice | `invalid_state`, no change |
| C10 | 2-cleaner job, 4h00m and 4h10m worked | second departs | invoice 18000 + 18750 = 36750 cents |
| C11 | one of two departed | list invoices | none for that job |
| C12 | invoice 36750 | pay 30000; pay 36750; pay again | refused; settled; refused |
| C13 | cleaner jobs 8–12, 13–17 | extend first by 20 min | second starts ≥ 13:20 (re-booked), cascade respected |
| C14 | any | extend by 30 min | `invalid_input` |
| C15 | extension ends job 17:40 | extend | accepted |
| C16 | 6 h worked Tue; 30 h in week | utilization | 6/8 (75%); 30/40 (75%) |
| C17 | zero worked time | depart at arrive time | $0.00 line |
| C18 | seeded random 1,000+ ops (lengths ~N(4.14, 1.75) clamped to (0, 9]) | book/extend/delete | invariants hold: no overlaps, earliest slot verified against brute-force oracle |
