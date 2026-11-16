# Feature Specification: Scheduling and Billing for a House-Cleaning Business

**Feature Branch**: `001-cleaning-scheduling-billing` (no branch created; work stays on `main`)

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Problem: scheduling and billing for a house-cleaning business (see problem.md). 12 cleaners, 2 back-office staff. Appointments are out of sync between field and back office, causing double bookings, overlapping jobs, large gaps in cleaners' days, and inaccurate, late invoices. Maximize cleaner utilization through effective appointment management and field/back-office communication. All data is synthetic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Book a job without conflicts (Priority: P1)

Back-office staff keep records of cleaners, clients and jobs. When a client asks for a cleaning, staff create a job for one client, specifying the number of cleaners needed (1, 2 or 3), the expected length, and the requested day. The system picks the cleaners itself and books the job into the earliest slot on or after the requested day in which enough cleaners are free.

**Why this priority**: Conflict-free booking is the core pain (double bookings, overlaps, gaps) and everything else depends on it.

**Independent Test**: Create cleaners, a client and several jobs; verify each job lands in the earliest valid slot, within working hours, with no cleaner double-booked or overlapped.

**Acceptance Scenarios**:

1. **Given** 12 cleaners with no jobs, **When** staff book a 4-hour, 2-cleaner job for a Monday, **Then** the job is booked Monday at 8:00–12:00 with two cleaners assigned by the system.
2. **Given** a cleaner whose job ends at 12:00, **When** another job is booked that would need that cleaner, **Then** that cleaner is not assigned a job starting before 13:00 (less than 1 hour after the earlier job ends counts as an overlap).
3. **Given** all cleaners are busy for the requested day, **When** a job is booked, **Then** it goes into the earliest later slot where enough cleaners are free, skipping weekends.
4. **Given** a requested job longer than a workday (more than 9 hours), **When** staff try to book it, **Then** it is refused with a clear message and nothing changes.
5. **Given** a requested day on a weekend, **When** a job is booked, **Then** it is placed on the next Monday at the earliest.
6. **Given** a job needing a number of cleaners other than 1, 2 or 3, **When** staff submit it, **Then** it is refused with an error and nothing changes.

---

### User Story 2 - Manage cleaners, clients and jobs (Priority: P1)

Back office can create, view, change and delete cleaners, clients and jobs. Deleting a cleaner who has future jobs re-books those jobs; deleting a client cancels their future jobs. Invoices already issued never change.

**Why this priority**: Records are the foundation, and removal rules protect the schedule's integrity.

**Independent Test**: Run create/read/update/delete on each record type; delete a cleaner with future jobs and a client with future jobs and verify the stated outcomes.

**Acceptance Scenarios**:

1. **Given** a cleaner with future jobs, **When** staff delete the cleaner, **Then** each of those jobs is booked again by the booking rule with the remaining cleaners, with no overlaps created.
2. **Given** a client with future jobs and an already-issued invoice, **When** staff delete the client, **Then** the future jobs are cancelled and the issued invoice is unchanged.
3. **Given** a request that refers to a record that does not exist, **When** staff submit it, **Then** an error is shown, nothing changes, and the app keeps working.
4. **Given** invalid input (blank name, non-numeric length), **When** staff submit it, **Then** the error is shown and no record is changed.

---

### User Story 3 - Record time in the field (Priority: P2)

A cleaner sees their jobs for the day. They tap Arrive on reaching a job and Depart on leaving. The time between the taps is that cleaner's time worked on the job.

**Why this priority**: Time worked drives accurate invoices and utilization.

**Independent Test**: For a booked job, record Arrive and Depart for a cleaner and verify the time worked is stored.

**Acceptance Scenarios**:

1. **Given** a cleaner with two jobs today, **When** they view their day, **Then** they see exactly those two jobs in time order.
2. **Given** a cleaner has arrived at a job, **When** they tap Depart, **Then** time worked is the elapsed time between Arrive and Depart.
3. **Given** a cleaner who has not arrived, **When** they tap Depart (or tap Arrive twice), **Then** an error is shown and nothing changes.

---

### User Story 4 - Invoice on completion and track settlement (Priority: P2)

A job is complete when the last of its cleaners departs. At that moment an invoice is issued charging $45 per hour per cleaner on each cleaner's time worked, rounded to the nearest cent, listing each cleaner's time. Each invoice is paid in full in one payment; back office can see which invoices are settled.

**Why this priority**: Accurate, timely invoicing is a stated business goal.

**Independent Test**: Complete a job with two cleaners of different worked times; verify the invoice appears at the last departure with correct itemization and total; pay it in full and verify it shows as settled.

**Acceptance Scenarios**:

1. **Given** a 2-cleaner job where one cleaner worked 4h 00m and the other 4h 10m, **When** the second departs, **Then** an invoice is issued listing both times and charging $180.00 + $187.50 = $367.50.
2. **Given** a job where only one of two cleaners has departed, **When** viewing invoices, **Then** no invoice exists yet.
3. **Given** an issued invoice of $367.50, **When** a payment of $300.00 is recorded, **Then** it is refused, the invoice stays unsettled, and the app continues working.
4. **Given** an issued invoice, **When** a payment of exactly its total is recorded, **Then** the invoice is marked settled.
5. **Given** a settled invoice, **When** another payment is attempted, **Then** it is refused.

---

### User Story 5 - Request more time on a job (Priority: P3)

A cleaner can ask for more time on a job in 20-minute steps, extending their schedule. If a later job of that cleaner would then start less than 1 hour after the extended job ends, the later job is booked again by the booking rule, starting no earlier than 1 hour after the extended job's new end. Any job bumped this way is re-booked the same way. Extensions may run past 17:00.

**Why this priority**: Real jobs overrun; the schedule must absorb that without creating conflicts.

**Independent Test**: Book back-to-back jobs for one cleaner, extend the first, and verify the later job moves and no overlap exists anywhere.

**Acceptance Scenarios**:

1. **Given** a cleaner's job ends at 12:00 and their next starts at 13:00, **When** they request 20 more minutes, **Then** the next job is re-booked to start no earlier than 13:20.
2. **Given** the re-booked job in turn pushes another job of a cleaner to within 1 hour, **When** the re-booking happens, **Then** that job is also re-booked by the same rule.
3. **Given** an extension that ends the job at 17:40, **When** it is granted, **Then** it is accepted (extensions may run past 17:00).
4. **Given** a request for a non-multiple of 20 minutes, **When** submitted, **Then** it is refused with an error and nothing changes.

---

### User Story 6 - See cleaner utilization (Priority: P3)

Back office sees, for each cleaner, billable hours worked out of 8 per workday and out of 40 per week.

**Why this priority**: It measures the headline goal but needs the other stories first.

**Independent Test**: With recorded time on several jobs, verify daily and weekly figures per cleaner.

**Acceptance Scenarios**:

1. **Given** a cleaner who worked 6 billable hours on a Tuesday, **When** staff view utilization for that day, **Then** it shows 6 of 8 hours (75%).
2. **Given** a cleaner who worked 30 billable hours in a week, **When** staff view the week, **Then** it shows 30 of 40 hours (75%).

---

### Edge Cases

- A job length of zero, negative, or longer than a 9-hour workday is refused; a length exactly 9 hours books 8:00–17:00.
- A job whose slot would end after 17:00 on a day is moved to a later day (start and end must both be within 8:00–17:00).
- A job needing more cleaners than exist (or than can ever be free) is refused with a clear message rather than looping forever.
- A cleaner is deleted and not enough cleaners remain to re-book a future job: the user is told, and the outcome for that job is reported rather than silently dropped.
- A cleaner departs without arriving, or arrives twice, or arrives at a job not assigned to them.
- A job is extended after it has already been completed and invoiced: refused; issued invoices never change.
- Client deleted while one of their jobs is in progress or has an unpaid invoice: future jobs are cancelled, issued invoices remain.
- Zero time worked yields a $0.00 invoice line; rounding to the nearest cent applies to each cleaner's charge.
- Any failure shows the error to the user, leaves data unchanged, and the app keeps working.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Back office MUST be able to create, read, update and delete cleaners, clients and jobs.
- **FR-002**: A job MUST be for exactly one client, require 1, 2 or 3 cleaners, and have an expected length; other values MUST be refused.
- **FR-003**: The system MUST assign cleaners itself; any free cleaners are acceptable.
- **FR-004**: The system MUST book each job into the earliest slot on or after the requested day in which enough cleaners are free.
- **FR-005**: Working hours MUST be 8:00–17:00, Monday to Friday; a booked job MUST start and end within them.
- **FR-006**: A job longer than a workday MUST be refused.
- **FR-007**: For any cleaner, a second job starting less than 1 hour after the first ends (or earlier) MUST count as an overlap; no booking, extension or re-booking may create an overlap or a double booking.
- **FR-008**: A cleaner MUST be able to see their jobs for a given day.
- **FR-009**: A cleaner MUST be able to record Arrive and Depart for a job; the interval between them is that cleaner's time worked on that job.
- **FR-010**: A cleaner MUST be able to request more time on a job in 20-minute steps, extending their schedule; extensions MAY run past 17:00.
- **FR-011**: When an extension leaves one of that cleaner's later jobs starting less than 1 hour after the extended job's new end, the later job MUST be re-booked by the booking rule, starting no earlier than 1 hour after the new end; any job bumped by this MUST be re-booked the same way.
- **FR-012**: When a cleaner with future jobs is deleted, those jobs MUST be re-booked by the booking rule.
- **FR-013**: When a client is deleted, their future jobs MUST be cancelled.
- **FR-014**: Invoices already issued MUST NOT change when a cleaner or client is deleted or a job is re-booked.
- **FR-015**: A job MUST be treated as complete when the last of its cleaners departs, and its invoice MUST be issued at that moment.
- **FR-016**: An invoice MUST charge $45 per hour for each cleaner on that cleaner's time worked, rounded to the nearest cent, and list each cleaner's time.
- **FR-017**: An invoice MUST be payable only in full by one payment; any other amount MUST be refused.
- **FR-018**: Back office MUST be able to see which invoices are settled and which are not.
- **FR-019**: The system MUST report, for each cleaner, billable hours worked out of 8 per workday and out of 40 per week.
- **FR-020**: On any error (bad input, nonexistent record, unmeetable request) the system MUST show the error to the user, change nothing, and keep working.
- **FR-021**: The back-office experience and the cleaner experience MUST follow the same scheduling, time and billing rules, and each MUST keep its data locally without needing any network service.

### Key Entities

- **Cleaner**: A field worker with a name; can be assigned to jobs; has a schedule and utilization figures.
- **Client**: A customer whose home is cleaned; owns jobs.
- **Job**: A cleaning appointment for one client; has number of cleaners needed (1–3), expected length, scheduled day/start/end, assigned cleaners, status (booked, in progress, complete, cancelled), and per-cleaner arrive/depart times.
- **Time Entry**: One cleaner's Arrive and Depart on one job; yields time worked.
- **Invoice**: Issued when a job completes; lists each cleaner's time and charge, total, and settlement status; immutable once issued except for being marked settled.
- **Payment**: A single full-amount payment against an invoice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every create, read, update and delete on cleaners, clients and jobs succeeds for valid input in 100% of tested cases.
- **SC-002**: Across a test set of at least 1,000 randomized bookings, extensions and re-bookings (job lengths averaging about 4.14 h, standard deviation about 1.75 h), zero double bookings and zero overlaps (under-1-hour gaps) occur.
- **SC-003**: 100% of invalid requests produce a visible error, change no data, and leave the app usable.
- **SC-004**: 100% of completed jobs have an invoice issued at the moment of the last departure, and 100% of invoice totals equal $45 × each cleaner's hours worked, rounded to the cent per cleaner.
- **SC-005**: 100% of payments for any amount other than the full invoice total are refused.
- **SC-006**: Back office can tell whether any given invoice is settled within one view, with no manual calculation.
- **SC-007**: Every job is booked into the earliest valid slot; no earlier slot with enough free cleaners exists in any verified case.
- **SC-008**: Utilization per cleaner for a day and a week can be viewed and matches billable hours worked in 100% of verified cases.

## Assumptions

- Users are 2 back-office staff and 12 cleaners; there is no sign-in or access control.
- Booking is by day only (requested day, not requested time); the system chooses the start time.
- Billable hours equal each cleaner's time worked (Arrive to Depart).
- Times are in a single local time zone; no travel time between jobs beyond the required 1-hour gap.
- "Future jobs" means jobs not yet started at the time of deletion.
- Out of scope: payroll, recurring appointments, maps, travel time, notifications, accounts and sign-in, email, payment processing, and synchronizing the two apps (each keeps its own local data).
- Two expressions of the same rules are delivered: a desktop experience for back office and a mobile logic layer for cleaners (no user interface for the latter).
- All data is synthetic.
