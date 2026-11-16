# Feature Specification: Cleaning Business Scheduling and Billing

**Feature Branch**: `001-cleaning-scheduling-billing`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Scheduling and billing for a house-cleaning business — two apps that follow the same rules, each keeping its data in its own local file: a desktop local web page served by Python for the back office, and a Swift package with no user interface holding the cleaner-side mobile logic. Full problem statement in problem.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Back office books a job into the earliest safe slot (Priority: P1)

A back-office staff member creates clients and cleaners, then books a job: for one client, needing 1, 2 or 3 cleaners, with an expected length. The system assigns the cleaners itself and places the job in the earliest slot, on or after the requested day, where enough cleaners are free — any free cleaners will do. Jobs start on the quarter hour inside the 8:00–17:00 Monday–Friday workday. A job longer than 8 hours is split into as many 8-hour parts as it needs, then the rest, on consecutive workdays with the same cleaners on every part. If no slot exists within 90 days past the requested day, the booking is refused with a message and nothing changes.

**Why this priority**: Booking without double bookings or overlaps is the core pain ("cleaners get double-booked, or booked into jobs that overlap"), and every other story consumes booked jobs.

**Independent Test**: With cleaners and clients on file, book jobs (short jobs, a job requested for a Saturday, an 8-hour job, a 10-hour job, and an over-full calendar) and verify placement, self-assignment, part splitting, and refusal — without any other story built.

**Acceptance Scenarios**:

1. **Given** cleaners free all week, **When** back office books a 2-cleaner job requested for a Tuesday, **Then** the job is placed at the earliest quarter-hour slot on or after that Tuesday where 2 cleaners are free, no earlier than 8:00.
2. **Given** a job requested for a Saturday, **When** it is booked, **Then** it starts Monday at 8:00.
3. **Given** a 10-hour job, **When** it is booked, **Then** it becomes two parts on consecutive workdays — 8 hours one workday, 2 hours the next — with the same cleaners on both parts; an 8-hour job fits one day (8:00 to 16:00).
4. **Given** no slot exists in the 90 days after the requested day, **When** a booking is attempted, **Then** it is refused with a message and nothing changes.
5. **Given** a cleaner's existing job ends at 12:10, **When** a new job is booked for that cleaner, **Then** it starts no earlier than 13:15 — the first quarter hour at least an hour later; after an end of 12:00, the next start may be 13:00 but not 12:45.

---

### User Story 2 - Cleaners tap Arrive and Depart in the field, and the invoice issues itself (Priority: P1)

A cleaner sees their jobs for the day. They tap Arrive when they get to a job and Depart when they leave; the time between the two taps is that cleaner's time worked on the job, recorded to the minute. A job is complete when the last of its cleaners departs, and its invoice is issued at that moment: $45 per hour for each cleaner on that cleaner's time worked, listing each cleaner's time. Each cleaner's line is rounded to the nearest cent, half a cent up; the invoice total is the sum of its lines.

**Why this priority**: Accurate, on-time invoices are the second headline pain ("invoices are inaccurate, and they go out late").

**Independent Test**: Given a booked job with assigned cleaners, tap Arrive/Depart for each cleaner (e.g. a cleaner who works 3 hours 30 minutes) and verify recorded minutes, line amounts (3 h 30 min → $157.50), half-up cent rounding, invoice timing at the last departure, and the total.

**Acceptance Scenarios**:

1. **Given** a cleaner with a booked job today, **When** the cleaner views their day, **Then** the job appears with its client, start time and expected length.
2. **Given** a 2-cleaner job where one cleaner has departed, **When** the second cleaner taps Depart, **Then** the invoice is issued at that moment.
3. **Given** a cleaner who taps Arrive at 9:00 and Depart at 12:30, **When** the invoice issues, **Then** that cleaner's line is $157.50 (3.5 h × $45/h).
4. **Given** cleaners whose worked minutes produce fractional cents, **When** the invoice issues, **Then** each line is rounded to the nearest cent, half a cent up, and the total equals the sum of the rounded lines.

---

### User Story 3 - Cleaners ask for more time without wrecking the rest of the day (Priority: P2)

A cleaner who has arrived on a job in progress can ask for more time in 20-minute steps, as many as needed, extending their schedule. When that leaves one of their later jobs less than 1 hour after the extended job's new end, the later job is booked again by the booking rule, starting no earlier than 1 hour after the extended job's new end. A job that this bumps is booked again the same way. Extensions may run past 17:00.

**Why this priority**: Real jobs overrun; without safe rebooking, overruns reintroduce exactly the overlaps this feature exists to remove. It builds on booking and time tracking.

**Independent Test**: Given a cleaner who has arrived on a job with a later booked job, take 20-minute extensions until the later job falls inside the 1-hour shadow, and verify the later job is rebooked by the booking rule from at least 1 hour after the new end, cascading where needed, leaving no overlap or double booking.

**Acceptance Scenarios**:

1. **Given** a cleaner who has tapped Arrive, **When** they request one more-time step, **Then** their job's end moves 20 minutes later and no other job changes when no later job violates the 1-hour shadow.
2. **Given** a later job left less than 1 hour after the extended end, **When** the extension lands, **Then** that later job is booked again by the booking rule, starting no earlier than 1 hour after the extended end.
3. **Given** a rebooking that bumps another job, **When** it happens, **Then** the bumped job is booked again the same way until nothing overlaps.
4. **Given** an extension that carries the job past 17:00, **When** it is applied, **Then** it is allowed.
5. **Given** a cleaner who has NOT tapped Arrive (or a finished job), **When** they request more time, **Then** it is refused with an error and nothing changes.

---

### User Story 4 - Records maintenance with safe deletions (Priority: P2)

Back office can create, read, update and delete cleaners, clients and jobs. Deleting a cleaner rebooks that cleaner's future jobs — jobs nobody has tapped Arrive on — with any free cleaners. Deleting a client cancels their future jobs. A job whose invoice has been issued can't be deleted, and issued invoices never change and are never deleted.

**Why this priority**: CRUD underpins everything, but the deletion/rebooking rules are their own slice of behavior on top of booking.

**Independent Test**: Exercise every create, read, update and delete on cleaners, clients and jobs, including deleting a cleaner with future and started jobs, deleting a client with future jobs, and attempting to delete an invoiced job or alter an issued invoice.

**Acceptance Scenarios**:

1. **Given** a cleaner with two future jobs and one arrived-on job, **When** the cleaner is deleted, **Then** the two future jobs are booked again by the booking rule with any free cleaners and the started job is untouched.
2. **Given** a client with future jobs, **When** the client is deleted, **Then** those future jobs are cancelled.
3. **Given** a job whose invoice has been issued, **When** back office tries to delete it, **Then** the deletion is refused and the job and invoice remain unchanged.
4. **Given** an update naming a record that doesn't exist (or bad input), **When** it is attempted, **Then** the error is shown, nothing changes, and the app carries on working.

---

### User Story 5 - Back office settles invoices (Priority: P2)

Back office sees which invoices are settled and which are not. An invoice is paid in full in one payment; a payment of any other amount is refused.

**Why this priority**: Billing only pays off if payment status is visible; it depends on issued invoices but nothing else.

**Independent Test**: Produce issued invoices, record one full payment and non-full payments, and verify settled/unsettled grouping and refusal of every other amount.

**Acceptance Scenarios**:

1. **Given** an unsettled invoice, **When** back office records one payment for its exact total, **Then** the invoice shows as settled.
2. **Given** an unsettled invoice, **When** back office records a payment of any other amount, **Then** it is refused and the invoice remains unsettled.
3. **Given** both settled and unsettled invoices, **When** back office views status, **Then** each invoice appears in the right group.

---

### User Story 6 - Cleaner utilization reporting (Priority: P3)

For each cleaner: billable hours worked out of 8 per workday, and out of 40 per week (Monday to Sunday). Work that runs past midnight counts on each day for the part worked that day. Hours may exceed 8 or 40.

**Why this priority**: Reporting serves the utilization goal but delivers nothing until booking, time tracking and invoices exist.

**Independent Test**: Supply known worked time (e.g. a cleaner who works 22:00 to 2:00) and verify per-day and per-week totals, including midnight-spanning splits and totals above 8/40.

**Acceptance Scenarios**:

1. **Given** a cleaner who worked 3 hours 30 minutes on Monday, **When** Monday's utilization is viewed, **Then** the cleaner shows 3.5 of 8 hours.
2. **Given** a cleaner who works from 22:00 to 2:00 spanning two days, **When** daily utilization is viewed, **Then** both days show 2 hours for that cleaner.
3. **Given** a cleaner who works 45 hours in a Monday–Sunday week, **When** weekly utilization is viewed, **Then** it shows 45 of 40 hours, not capped.
4. **Given** a cleaner with no worked time in a period, **When** utilization is viewed, **Then** they show 0 hours, not an error.

---

### Edge Cases

- End 12:00 → next start may be 13:00 but not 12:45; end 12:10 → next start 13:15 (the first quarter hour at least an hour later). Overlap = second starts less than 1 hour after first ends.
- A job requested for a Saturday is booked from Monday at 8:00; a booking finding no slot in the 90 days after the requested day is refused with a message and nothing changes.
- An 8-hour job fits one day (8:00 to 16:00); a 10-hour job is two parts (8 h + 2 h) with the same cleaners on both.
- DST/clock-change days: jobs still start and end within 8:00–17:00 local time; the calendar's clock changes apply; there are no holidays.
- More time requested by a cleaner who hasn't arrived, before the job starts, or after it finished: refused with an error, nothing changes.
- Extension cascades touch only future jobs (nobody has tapped Arrive); an already-arrived job is never moved.
- Arrive twice, or Depart with no prior Arrive: refused with an error, nothing changes.
- Deleting a cleaner with no future jobs, or a client with no future jobs: the record is removed with nothing to rebook or cancel.
- Updating or deleting an issued invoice, or deleting a job whose invoice was issued: refused.
- Payment on an already-settled invoice, a second payment on a settled invoice, or payment for an invoice that doesn't exist: refused, nothing changes.
- Any failing operation (bad input, missing record, unmet request) must show the error, change nothing, and leave the app working.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Back office MUST be able to create, read, update and delete cleaners, clients and jobs; each app keeps its records in its own local file, and the two apps follow the same rules without being connected.
- **FR-002**: A job MUST be for one client, need 1, 2 or 3 cleaners, and have an expected length (population average about 4.14 hours, standard deviation about 1.75 hours). The system MUST assign the cleaners itself; any free cleaners will do.
- **FR-003**: Booking MUST place the job in the earliest slot, on or after the requested day, where enough cleaners are free. Jobs MUST start on the quarter hour (8:00, 8:15, 8:30, …).
- **FR-004**: The booking search MUST look up to 90 days past the requested day; if there is no slot by then, the booking MUST be refused with a message and nothing may change.
- **FR-005**: A workday MUST run 8:00 to 17:00, Monday to Friday, and a booked job MUST start and end within those hours. Times are the business's local time and the calendar's clock changes apply. There are no holidays.
- **FR-006**: A job longer than 8 hours MUST be split across consecutive workdays — as many 8-hour parts as it needs, then the rest — with the same cleaners on every part, each part booked by the booking rule.
- **FR-007**: Two jobs for the same cleaner overlap when the second starts less than 1 hour after the first ends. No booking, extension or rebooking may create an overlap or a double booking.
- **FR-008**: A cleaner MUST be able to see their jobs for the day and tap Arrive and Depart; the time between the two taps, recorded to the minute, is that cleaner's time worked on the job.
- **FR-009**: A cleaner who has arrived on a job in progress MUST be able to request more time in 20-minute steps, as many as needed, extending their schedule. Extensions may run past 17:00.
- **FR-010**: When an extension leaves one of the cleaner's later jobs less than 1 hour after the extended job's new end, that later job MUST be booked again by the booking rule, starting no earlier than 1 hour after the extended job's new end; a job that this bumps MUST be booked again the same way (cascading).
- **FR-011**: A future job is one nobody has tapped Arrive on. Deleting a cleaner with future jobs MUST have those jobs booked again by the booking rule with any free cleaners. Deleting a client MUST cancel their future jobs.
- **FR-012**: A job whose invoice has been issued cannot be deleted. Issued invoices never change and are never deleted.
- **FR-013**: A job is complete when the last of its cleaners departs, and its invoice MUST be issued at that moment, charging $45 per hour for each cleaner on that cleaner's time worked and listing each cleaner's time. Each cleaner's line MUST be rounded to the nearest cent, half a cent up, and the invoice total MUST be the sum of its lines (3 hours 30 minutes → $157.50).
- **FR-014**: An invoice MUST be settled by one payment of its exact full total; a payment of any other amount MUST be refused. Back office MUST be able to see which invoices are settled and which are not.
- **FR-015**: Utilization MUST be reportable per cleaner as billable hours worked out of 8 per workday and out of 40 per week (Monday to Sunday); work past midnight counts on each day for the part worked that day; hours may exceed 8 or 40.
- **FR-016**: On any error (bad input, a record that doesn't exist, a request that can't be met) the app MUST NOT crash: it shows the error to the person using it, changes nothing, and carries on working.
- **FR-017**: The apps MUST enforce nothing beyond these rules — no booking notice, payment due dates or similar rules of the developer's own.

### Key Entities

- **Cleaner**: A person who works at clients' homes (12 on staff). Identified for scheduling and time tracking; their booked jobs form their schedule.
- **Client**: The household a job is for. One client per job; deleting a client cancels their future jobs.
- **Job**: One piece of cleaning for one client needing 1–3 cleaners, with a requested day and an expected length (average ~4.14 h, standard deviation ~1.75 h). May be split into parts on consecutive workdays with the same cleaners on every part. Records per-cleaner Arrive/Depart taps to the minute and per-cleaner time worked. Future until someone taps Arrive; complete when the last cleaner departs.
- **Invoice**: Issued the moment its job completes. Lists each cleaner's time and a line at $45/hour on that cleaner's time worked (rounded to the nearest cent, half a cent up); total = sum of lines. Immutable once issued, never deleted. Settled or unsettled.
- **Payment**: A one-shot settlement of an invoice; only a single payment for the exact total is accepted. Work past midnight in its hours feeds each day's utilization.
- **Utilization**: Per-cleaner derived report: billable hours worked out of 8 per workday and 40 per Monday–Sunday week; may exceed both.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every create, read, update and delete on cleaners, clients and jobs works without error.
- **SC-002**: No booking, extension or rebooking ever leaves a double booking or an overlap (verified, e.g., by the 12:00→13:00-not-12:45 and 12:10→13:15 boundary cases).
- **SC-003**: On any error the app doesn't crash: the person using it sees the error, nothing changes, and the app carries on working.
- **SC-004**: Every invoice is complete (issued the moment the last cleaner departs, listing every cleaner's time) and accurate (each line $45/h on that cleaner's taps to the minute, rounded to the nearest cent half-up; a 3 h 30 min cleaner costs $157.50; total = sum of lines).
- **SC-005**: Back office can track which invoices are settled; only a single full-total payment settles an invoice, every other amount is refused.
- **SC-006**: A job requested for a day with no availability within 90 days past the requested day is refused with a message and nothing changes.

## Assumptions

- The desktop back-office app is a local web page served by Python; the mobile cleaner app is a Swift package holding the app's logic with no user interface. Both encode the same rules and each keeps its data in its own local file; connecting them is out of scope.
- "Back office" users are the 2 back-office staff; "cleaner" users are the 12 cleaners. No accounts or sign-in exist (out of scope), so both apps assume their operator is who they say they are.
- Staff/client records are created by the back office; the problem statement gives no cleaner self-service signup.
- The requested day of a job is supplied by back office at booking time; bookings before 8:00 on a workday resolve to 8:00 that day, weekend requests to Monday 8:00.
- Utilization counts only tapped (billable) time between Arrive and Depart, not booked-but-no-show time.
- A cleaner's day jobs list shows the jobs assigned to them starting that day.
- Out of scope, per the problem statement: payroll, recurring appointments, maps, travel time, notifications, accounts and sign-in, email, payment processing, and syncing the two apps.
- No network services, accounts or outside data; all data is synthetic.
