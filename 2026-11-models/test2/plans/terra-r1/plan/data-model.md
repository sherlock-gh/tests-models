# Data model: Cleaning Scheduling and Billing

This is a logical model for each independent local store. IDs are stable within that store; the two expressions do not exchange or synchronize data. Storage representation is an implementation choice. Dates, local scheduled times and actual instants must be represented consistently so comparisons and elapsed-time calculations are unambiguous.

## Records and relationships

| Entity | Fields | Relationships and invariants |
| --- | --- | --- |
| Cleaner | ID, name, active/deleted marker | Has assignments and historical work records. A removed cleaner cannot receive new assignments; historical identity remains available for billing and utilization. |
| Client | ID, name, active/deleted marker | Has jobs and invoices. Removal cancels future jobs but preserves issued invoices and the historical identity they contain. |
| Job | ID, client ID, requested day, expected duration, required cleaner count, scheduled start and end, status | Exactly one client; one to three assignments. Duration is positive and at most nine hours. Normal scheduled intervals are on one weekday between 08:00 and 17:00; an active job's extended end can exceed 17:00. |
| Assignment / work record | Job ID, cleaner ID, arrival instant, departure instant | Unique per job and cleaner. Arrival and departure are initially absent; departure requires a prior arrival and cannot precede it. Worked time is the actual elapsed interval, not scheduled duration. |
| Invoice | ID, job ID, issued instant, client identity snapshot, line snapshots, total in cents, settlement status | Exactly one invoice per completed job. Snapshot each assigned cleaner's identity and elapsed time at issue; preserve billing details despite later edits or deletions. Total is the sum of actual elapsed cleaner time at $45/hour, rounded once to the nearest cent. |
| Payment | ID, invoice ID, amount in cents, recorded instant | At most one per invoice; amount equals its full total. Its presence marks the invoice settled. |

A job's scheduled interval is shared by all its assigned cleaners. A cleaner's consecutive scheduled jobs must have at least one hour between the earlier end and later start. Intervals ending exactly at 17:00 and gaps of exactly one hour are valid. The booking rule selects the earliest eligible start on or after the requested day with enough available cleaners; ties may use any eligible set. A rebooking caused by an extension has the additional lower bound of one hour after the extended end (or the relevant displacement bound for a cascade). A normal booking never spans workdays, and weekends are skipped.

## Lifecycle and changes

- A newly booked job is **scheduled**. Its first arrival makes it **in progress**; each assigned cleaner may arrive and depart once, in that order. The last departure makes it **completed** and issues its invoice in the same atomic operation.
- An active job may be extended by positive multiples of 20 minutes. Update its scheduled end and rebook affected later jobs and any cascading displacements before committing. Rebookings use normal hours and the applicable lower bound.
- A future job is unstarted and has a scheduled start after the removal instant. Deleting its client **cancels** it; deleting an assigned cleaner rebooks it with remaining cleaners. In-progress work is retained through completion. Records needed for issued invoices remain available.
- Availability-affecting edits to a scheduled job are fresh bookings no earlier than its requested day. A completed job's historical billing snapshot must not change. Deletion or editing must preserve issued invoices and their settlement status.
- Every mutation, including all resulting rebookings and invoice issuance, commits as one unit. Invalid, missing, or unsatisfiable requests leave all records unchanged.

## Derived utilization

For a cleaner and a selected workday, sum actual elapsed time on completed, invoiced jobs attributed to the day worked; show that value against eight hours. For a selected Monday–Sunday week, sum time attributed to days in that week and show it against 40 hours. Split a work interval at day boundaries for attribution if needed. Values may exceed the denominators. Invoice snapshots or retained work records provide the source of truth.
