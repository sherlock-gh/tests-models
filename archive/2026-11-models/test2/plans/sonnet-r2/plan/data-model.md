# Data Model

Both apps store the same logical model (one JSON file each). Times: dates are ISO `YYYY-MM-DD`; schedule times are minutes from midnight; Arrive/Depart are local ISO timestamps to the second; money is integer cents.

## Cleaner
| Field | Rule |
|---|---|
| id | integer, unique, never reused |
| name | required, non-blank |

## Client
| Field | Rule |
|---|---|
| id | integer, unique, never reused |
| name | required, non-blank |
| address | optional text (synthetic) |

## Job
| Field | Rule |
|---|---|
| id | integer, unique |
| clientId | must reference an existing client |
| cleanersNeeded | integer 1, 2 or 3 |
| lengthMinutes | integer > 0 and ≤ 540 (9 h) at booking |
| requestedDate | weekday or weekend date |
| date, startMinute | scheduled slot; start ≥ 480 (8:00), start + length ≤ 1020 (17:00) at booking; weekday only |
| endMinute | start + length + extensions (may exceed 1020) |
| cleanerIds | exactly `cleanersNeeded` distinct existing cleaners |
| status | `booked` → `in_progress` → `complete`; or `cancelled` |
| timeEntries | one per assigned cleaner (below) |

**Invariants** (hold after every operation): for any cleaner, any two non-cancelled jobs on the same date have the later start ≥ earlier end + 60 min (jobs never span dates); no cleaner appears twice in a job; a job's slot is the earliest valid one at the time of booking.

## Time Entry
| Field | Rule |
|---|---|
| jobId, cleanerId | cleaner must be assigned to the job |
| arrivedAt | set once; second Arrive refused |
| departedAt | requires arrivedAt, must be ≥ arrivedAt; set once |
| secondsWorked | departedAt − arrivedAt |

## Invoice
Created when the last assigned cleaner departs (job → `complete`); never edited except settlement.
| Field | Rule |
|---|---|
| id, jobId | one invoice per job |
| clientName | snapshot at issue |
| lines[] | per cleaner: cleanerName (snapshot), secondsWorked, chargeCents = (seconds × 5 + 2) // 4 |
| totalCents | sum of line charges |
| settled | false until a payment equals totalCents |

## Payment
| Field | Rule |
|---|---|
| invoiceId | existing, unsettled invoice |
| amountCents | must equal invoice totalCents exactly |
| paidAt | timestamp |

## State transitions
- Job: `booked` → (first Arrive) `in_progress` → (last Depart) `complete` + invoice issued. `booked` → `cancelled` on client delete. Complete/cancelled jobs cannot be extended or re-booked.
- Invoice: unsettled → settled (one full payment); settled invoices accept no payment.

## Derived: Utilization
Per cleaner and date: sum of secondsWorked of entries with arrivedAt on that date ÷ 8 h. Per week (Mon–Sun): ÷ 40 h.
