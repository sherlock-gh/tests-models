# Contract: Operations (shared by both apps)

Each operation either succeeds and commits, or fails with an error `{code, message}` and changes nothing. Error codes: `invalid_input`, `not_found`, `unschedulable`, `invalid_state`, `payment_mismatch`.

| Operation | Input | Result / key rules |
|---|---|---|
| createCleaner / updateCleaner / deleteCleaner / listCleaners / getCleaner | name | Delete re-books the cleaner's not-started jobs (all-or-nothing, else `unschedulable`) |
| createClient / updateClient / deleteClient / list / get | name, address | Delete cancels not-started jobs; issued invoices unchanged |
| bookJob | clientId, cleanersNeeded (1–3), lengthMinutes, requestedDate | Earliest slot ≥ requested date (weekend → Monday), 8:00–17:00, ≥ 60 min gap per cleaner, lowest-id free cleaners; length > 540 or ≤ 0 → `invalid_input`; not enough cleaners ever → `unschedulable` |
| updateJob | jobId, client / length / cleanersNeeded / requestedDate | Not-started jobs only; re-books by the booking rule; else `invalid_state` |
| deleteJob | jobId | Not-started jobs only |
| listJobs / getJob / cleanerDay | cleanerId, date | Day view sorted by start time |
| arrive | jobId, cleanerId, timestamp | Cleaner must be assigned, not yet arrived |
| depart | jobId, cleanerId, timestamp | Requires arrive; last depart completes job and issues invoice |
| requestExtension | jobId, cleanerId, minutes | Positive multiple of 20; job not complete/cancelled; cascading re-book (research D6) |
| listInvoices / getInvoice | filter settled/unsettled | Includes per-cleaner lines and total |
| payInvoice | invoiceId, amountCents | Must equal total, invoice unsettled, else `payment_mismatch` / `invalid_state` |
| utilization | cleanerId, date | Day hours of 8, week hours of 40, percentages |

Money: charge per cleaner = (secondsWorked × 5 + 2) // 4 cents. Gap rule: later start ≥ earlier end + 60 min.
