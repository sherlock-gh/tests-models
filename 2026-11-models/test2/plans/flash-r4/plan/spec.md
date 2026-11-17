# Feature Specification: Cleaning Business Scheduling and Billing

**Feature Branch**: `001-cleaning-scheduling-billing`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Scheduling and billing for a house-cleaning business: two disconnected apps — a back-office desktop app (local web page) and a cleaners' mobile app logic (no UI) — each keeping its data in its own local file."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Book a job conflict-free (Priority: P1)

Back-office staff enter a cleaning request: the client, how many cleaners the job needs
(1, 2 or 3), the expected length in hours, and the day the client wants it. The system
picks the cleaners and the start time itself: the earliest quarter-hour slot, on or after
the requested day, inside the workday (8:00–17:00, Monday–Friday), where enough cleaners
are free. Two of a cleaner's jobs conflict when the second starts less than 1 hour after
the first ends. A job longer than 8 hours is split into as many 8-hour parts
as needed plus the remainder, on later workdays. Each part is booked independently by
the booking rule, preferring the first part's cleaners when free and using other free
cleaners otherwise. If no slot exists within 90 days past the requested day, the booking is refused with a message
and nothing changes.

**Why this priority**: double-bookings, overlaps and empty gaps are the stated pain;
correct conflict-free booking is the heart of the feature.

**Independent Test**: with cleaners and clients on file, submit booking requests and
verify chosen days/times/cleaners, the quarter-hour grid, the 1-hour spacing, multi-day
splits, weekend skipping, and the 90-day refusal — without any other story implemented.

**Acceptance Scenarios**:

1. **Given** a job needs 2 cleaners on Monday and enough are free, **When** it is booked, **Then** 2 distinct cleaners are assigned and it starts at a quarter hour (8:00, 8:15, …) no earlier than 8:00 that Monday, with no cleaner holding another job that starts less than 1 hour after this one ends or ends less than 1 hour before this one starts.
2. **Given** a cleaner's job ends at 12:00, **When** booking their next job, **Then** 13:00 is the earliest allowed start — 12:45 is not.
3. **Given** a cleaner's job ends at 12:10, **When** booking their next job, **Then** 13:15 is the earliest allowed start — the first quarter hour at least 1 hour later.
4. **Given** a job is requested for a Saturday, **When** it is booked, **Then** it starts Monday at 8:00.
5. **Given** a 10-hour job, **When** it is booked, **Then** it is 8 hours one workday and 2 hours on a later workday, each independently booked by the booking rule, with the first part's cleaners on the second if free and other free cleaners otherwise; an 8-hour job fits a single day (e.g. 8:00–16:00).
6. **Given** no slot exists in the 90 days after the requested day, **When** booking is attempted, **Then** the request is refused with a message and no job or assignment is created.

---

### User Story 2 - Record time in the field with Arrive/Depart taps (Priority: P1)

A cleaner opens their day and sees their booked jobs. On arrival at a job they tap
Arrive; when they leave they tap Depart. The time between the two taps is that cleaner's
time worked on that job, recorded to the minute.

**Why this priority**: taps are the only source of truth for time worked, and time worked
is the basis of every invoice; without them nothing can be billed correctly.

**Independent Test**: book jobs, tap Arrive/Depart, and verify each cleaner's recorded
time equals tap-to-tap duration to the minute — testable without invoicing.

**Acceptance Scenarios**:

1. **Given** a cleaner has jobs today, **When** they view their day, **Then** they see those jobs with their times, client and assigned co-workers.
2. **Given** a cleaner taps Arrive at 8:00 and Depart at 11:30, **When** their time on that job is reviewed, **Then** it is 3 hours 30 minutes.
3. **Given** a cleaner has tapped Arrive on a job, **When** they tap Depart, **Then** the departure is recorded to the minute and the job stops accruing time for them.

---

### User Story 3 - Invoice on completion, settle in full (Priority: P2)

When the last of a job's cleaners taps Depart, the job is complete and its invoice is
issued at that moment: $45 per hour per cleaner on each cleaner's time worked, each
cleaner's line rounded to the nearest cent (half a cent up), the total being the sum of
the lines, and the invoice lists each cleaner's time. Back office sees which invoices are
settled. A payment must be the exact invoice total; any other amount is refused. Issued
invoices never change and are never deleted.

**Why this priority**: accurate, on-time invoices are the second stated pain; it builds
on the records and taps above.

**Independent Test**: complete jobs with known tap times and verify invoice contents,
rounding ($157.50 for 3 hours 30 minutes), totals, refusal of partial payments, and
settled/unsettled status — independently of booking choices.

**Acceptance Scenarios**:

1. **Given** a 2-cleaner job where cleaner A worked 3:30 and cleaner B worked 4:00, **When** the last cleaner departs, **Then** an invoice is issued immediately with lines $157.50 and $180.00 and total $337.50, listing each cleaner's time.
2. **Given** an issued invoice for $337.50, **When** a back-office staff member records a payment of $337.00, **Then** the person entering it is shown a message (they stay in control of the app, and the entry field is left with them) and the invoice stays unsettled.
3. **Given** a $337.50 invoice, **When** a payment of exactly $337.50 is recorded, **Then** the invoice shows as settled.
4. **Given** a job whose invoice has been issued, **When** back office tries to delete the job, **Then** the deletion is refused with a message and the job remains.

---

### User Story 4 - Ask for more time on a job in progress (Priority: P2)

While a cleaner is on a job (after Arrive, before Depart) they can ask for more time in
20-minute steps, as many as needed. Each step extends that cleaner's schedule past the
job's end. If the extension leaves one of their later jobs starting less than 1 hour
after the extended end, that later job is booked again by the booking rule, no earlier
than 1 hour after the extended end; anything that booking bumps is re-booked the same
way, repeatedly. Extensions may run past 17:00.

**Why this priority**: jobs realistically overrun; without it, overruns silently create
the very overlaps P1 forbids.

**Independent Test**: arrive on a job, add 20-minute steps, and verify the cleaner's
schedule extends, later jobs cascade-rebook per the booking rule with the ≥1-hour floor,
and nothing ever overlaps — testable without invoicing.

**Acceptance Scenarios**:

1. **Given** a cleaner has arrived on a job ending 12:00 with a later job booked at 13:15, **When** they take three 20-minute steps (new end 13:00), **Then** the later job (starting 13:15, less than 1 hour after 13:00) is re-booked by the booking rule starting no earlier than 14:00.
2. **Given** a cleaner takes steps pushing their work to 18:20, **When** the steps are recorded, **Then** they are accepted even though 17:00 has passed.
3. **Given** a re-booking triggered by an extension would bump another job, **When** it does, **Then** the bumped job is re-booked the same way, and every cleaner's schedule remains overlap- and double-free.

---

### User Story 5 - CRUD for cleaners, clients and jobs; safe removals (Priority: P2)

Back office creates, reads, updates and deletes cleaners, clients and jobs. A *future
job* is one nobody has tapped Arrive on. Deleting a cleaner re-books their future jobs
with any free cleaners via the booking rule; deleting a client cancels their future jobs.
A job with an issued invoice cannot be deleted.

**Why this priority**: records are the substrate for everything else, and removals are
where orphaned bookings would reintroduce chaos.

**Independent Test**: exercise every create/read/update/delete and both removal cascades
and verify the inventory and schedules stay consistent — independent of invoicing.

**Acceptance Scenarios**:

1. **Given** a cleaner has two future jobs, **When** the cleaner is deleted, **Then** the cleaner is gone and both jobs still exist, re-booked by the booking rule with free cleaners.
2. **Given** a client has one future job and one job already arrived at, **When** the client is deleted, **Then** the client and the future job are cancelled and the arrived-at job and its later invoice are untouched.
3. **Given** a nonexistent record id, **When** back office updates or deletes it, **Then** a message explains the record doesn't exist, nothing changes, and the app keeps working.

---

### User Story 6 - See utilization per cleaner (Priority: P3)

For each cleaner: billable hours worked out of 8 per workday and out of 40 per week
(Monday–Sunday). Work past midnight counts on each calendar day for the part worked that
day; hours may exceed 8 or 40.

**Why this priority**: management insight supporting the utilization goal; nothing else
depends on it.

**Independent Test**: enter worked time (including overnight spans) and verify daily and
weekly totals — testable purely from tap data.

**Acceptance Scenarios**:

1. **Given** a cleaner who works 22:00 to 2:00, **When** utilization is viewed, **Then** 2 hours count on the first day and 2 hours on the second.
2. **Given** a cleaner who worked 9 hours on Monday, **When** utilization is viewed, **Then** Monday shows 9 of 8 (overage shown, not capped).

---

### Edge Cases

- Job ending exactly on a quarter hour vs. off-quarter (e.g. 12:10 → next start 13:15).
- Requested day is a weekend/holiday-free gap: Saturday request books Monday 8:00; there are no holidays.
- Job length is not a whole number of hours; remainder part after 8-hour parts (10 h → 8+2).
- A job longer than 8 h ending exactly at 17:00 on a part day; parts must fit 8:00–17:00.
- 90-day horizon exhausted → refusal with message, no partial writes.
- Extension while other assigned cleaners have later jobs (Q1: job moves as a unit).
- Overnight extension (22:00–2:00) splitting utilization across two days and weeks.
- Depart without a prior Arrive, or a second Arrive → refused with message, nothing changes.
- Payment in wrong amount → refused; payment of exact total → settled.
- Deleting a cleaner/client/job whose targets don't exist → message, no crash.
- Clock-change days (spring forward / fall back) inside a multi-day job or workday.
- Concurrency between taps and back-office edits: each app only ever sees its own file (the two are not connected); within one app, an operation either fully applies or fully fails.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let back office create, read, update and delete cleaners, clients and jobs, each identified within its app's data on that machine.
- **FR-002**: System MUST book a job for one client requiring 1, 2 or 3 cleaners with a given expected length, assigning the cleaners itself from the available pool (12 cleaners).
- **FR-003**: System MUST book each job into the earliest slot on or after the requested day, on the quarter-hour grid (from 8:00), inside the 8:00–17:00 Monday–Friday workday, at which at least the required number of cleaners are free.
- **FR-004**: System MUST treat two of a cleaner's jobs as conflicting when the second starts less than 1 hour after the first ends, and MUST never create, extend or re-book into an overlap or double booking.
- **FR-005**: System MUST split a job longer than 8 hours into as many 8-hour parts as needed plus a final shorter part, on later workdays. Each part MUST be booked independently by the booking rule (FR-003/FR-004), preferring the first part's cleaners if free and assigning other free cleaners if not.
- **FR-006**: System MUST search up to 90 days past the requested day; when no slot exists, it MUST refuse the booking with a message and change nothing.
- **FR-007**: System MUST interpret all booked times in the business's local time and MUST observe the calendar's clock changes.
- **FR-008**: Mobile MUST show a cleaner their jobs for the day; a cleaner MUST be able
  to tap Arrive on a booked job part they are assigned to and Depart on a part they have
  arrived on; both taps MUST be recorded to the minute.
- **FR-009**: System MUST compute each cleaner's time worked on a job as Depart minus Arrive for that cleaner on that job.
- **FR-010**: A cleaner who has arrived on a job MUST be able to request more time in 20-minute steps, any number of times, extending that cleaner's end time; extensions MAY pass 17:00.
- **FR-011**: When an extension leaves any later job of that cleaner starting less than 1 hour after the extended end, the system MUST re-book that later job by the booking rule (FR-003/FR-004) with a start no earlier than 1 hour after the extended end, and MUST re-book any job it in turn bumps by the same rule until nothing conflicts.
- **FR-012**: System MUST define a future job as one on which nobody has tapped Arrive; deleting a cleaner MUST re-book their future jobs by the booking rule with any free cleaners; deleting a client MUST cancel that client's future jobs.
- **FR-013**: System MUST refuse to delete a job whose invoice has been issued; issued invoices MUST never change or be deleted.
- **FR-014**: System MUST mark a job complete when its last assigned cleaner taps Depart, and MUST issue its invoice at that moment.
- **FR-015**: System MUST price an invoice at $45 per hour per cleaner on that cleaner's time worked; each cleaner's line MUST be rounded to the nearest cent, half a cent up; the total MUST be the sum of the lines; the invoice MUST list each cleaner's time.
- **FR-016**: System MUST accept settlement only as one payment of exactly the invoice total; any other amount MUST be refused with a message; back office MUST be able to see which invoices are settled and which are not.
- **FR-017**: System MUST report per cleaner, per workday: billable hours worked out of 8, and per Monday–Sunday week out of 40; work crossing midnight MUST count each calendar day's portion on that day; totals MAY exceed 8/40.
- **FR-018**: System MUST deliver two independent apps with identical rules, each keeping its data only in its own local file, persisting across restarts on the same machine: a back-office desktop app presented as a local web page served by Python, and a cleaners' mobile app provided as a Swift package containing the logic without any user interface. The two apps are never connected.
- **FR-019**: On any error (bad input, missing record, impossible request), the app MUST NOT crash: it MUST show the error message to the person using it, apply no changes, and remain usable.
- **FR-020**: System MUST NOT add rules beyond those stated here — no booking notices, payment due dates, holidays, travel time, payroll, recurring appointments, maps, notifications, accounts/sign-in, email, or payment processing.

### Key Entities *(include if feature involves data)*

- **Cleaner**: a person who performs jobs; has identifying contact details; holds a schedule of job parts and taps; has utilization derived from worked time (8/day, 40/week baselines).
- **Client**: the householder who requests cleaning; has identifying contact details and address; owns jobs.
- **Job**: one client's cleaning work needing 1–3 cleaners with an expected length; has one or more *parts* (scheduled pieces of ≤8 h, each independently booked on a later workday than the preceding part); tracks completion via all cleaners having departed.
- **Assignment**: the pairing of cleaner to job part; carries that cleaner's Arrive and Depart taps (to the minute) and derived time worked.
- **Invoice**: issued at completion; one per job; lists each cleaner's time and line amount at $45/h, rounded half-cent-up per line; has a total; is settled by one exact payment; immutable once issued.
- **Payment**: a single settlement event recording the invoice total; wrong amounts never become payments.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of create/read/update/delete operations on cleaners, clients and jobs complete without errors or crashes across normal and error inputs.
- **SC-002**: Across a simulated season of bookings, extensions and re-bookings, 0 cleaner schedules ever contain a double booking or an overlap (a job starting less than 1 hour after another ends).
- **SC-003**: Every completed job's invoice is issued at the moment of the last Depart tap and its per-cleaner lines and total match $45/h arithmetic (half-cent-up line rounding) on 100% of checked invoices (e.g. 3 h 30 min → $157.50).
- **SC-004**: Back office can state, at any time, which invoices are settled and which are not, with 0 partial payments ever accepted.
- **SC-005**: Every error condition (bad input, nonexistent record, unmeetable request) shows the person a message, changes nothing, and leaves the app working — 0 crashes observed.
- **SC-006**: Back-office staff can go from opening the app to a confirmed booking (client, cleaners, day chosen by the system) without performing scheduling math themselves, in one interaction.
- **SC-007**: Utilization for each cleaner is readable per workday (out of 8) and per Monday–Sunday week (out of 40), with the 22:00–2:00 example splitting exactly 2/2 (overnight spans split by calendar day).

## Assumptions

- The business has 12 cleaners and 2 back-office staff; the workforce size is data, not a
  hard-coded limit — the booking rule works for whatever cleaner records exist.
- Typical workload: jobs average ~4.14 hours with a standard deviation of ~1.75 hours;
  this shapes testing data, not behavior.
- Times and durations that problem.md leaves open (client names/addresses/phones, free
  text) are stored as supplied without validation beyond being present; the rate ($45/h),
  grid (15 min), spacing (1 h), day (8:00–17:00 Mon–Fri), split size (8 h) and horizon
  (90 days) are exact, per problem.md.
- "Any free cleaners will do" means the booking rule may pick any qualifying set; the
  spec does not require preferring the least-utilized cleaner.
- Utilization's "billable hours worked" is tap-to-tap time (FR-009), including extensions.
- A job nobody arrived on contributes 0 worked hours (and, if it somehow completed via
  other cleaners, would invoice that cleaner at $0.00); completion still requires every
  assigned cleaner to depart.
- Clock changes affect wall-clock scheduling inside the business's local timezone; jobs
  are still measured by the clock times booked (a 2-hour job 8:00–10:00 across a
  spring-forward night occupies the clock span as booked). Worked time is tap-to-tap and
  uses real elapsed local time.
- Both apps enforce the same rules independently on their own files (Q6/Q-A4 context:
  they are not connected — reconciliation between them is out of scope).
- The mobile logic package exposes the cleaner-facing operations (see today's jobs,
  arrive, depart, more time) as testable logic; whoever runs it supplies the cleaner's
  identity (no accounts, sign-in out of scope).
- Decisions in questions.md (bumped jobs move as a unit; no automatic re-booking on edit
  but overlap rule enforced on edits; arrive-out-of-order allowed; one shared workday for
  all cleaners) are the working interpretation pending owner confirmation.
