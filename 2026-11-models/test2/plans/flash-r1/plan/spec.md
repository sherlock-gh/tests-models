# Feature Specification: Cleaning Scheduling and Billing

**Feature Branch**: `001-cleaning-scheduling-billing`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "scheduling and billing for a house-cleaning business: 12 cleaners, 2 back-office staff; job booking, arrival/departure taps, extensions, invoices, settlement, utilization"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Back office books jobs without conflicts (Priority: P1)

A back-office staff member registers clients and cleaners, then books a job for a client: they say which client, how many cleaners are needed (1, 2 or 3), the expected length in hours and the requested day. The system assigns the cleaners on its own and books the job into the earliest slot, on or after the requested day, where enough cleaners are free. The staff member can list, view, edit and remove cleaners, clients and jobs.

**Why this priority**: Booking without double-bookings or overlaps is the core pain today; time tracking and billing depend on clean job records.

**Independent Test**: Create cleaners and clients, book a series of jobs under varying demand, then verify no cleaner holds two jobs where the second starts less than 1 hour after the first ends, every scheduled job sits inside 8:00–17:00 Monday–Friday, and each job landed in the earliest feasible slot. Deliverable: conflict-free, earliest-slot booking with full record management.

**Acceptance Scenarios**:

1. **Given** three free cleaners and an empty schedule, **When** the back office books a 3-cleaner job of 4 hours requested for next Monday, **Then** the job is booked on the earliest workday at or after that Monday with three free cleaners, starting as early as allowed within 8:00–17:00.
2. **Given** a cleaner already booked 8:00–12:00 on Tuesday, **When** a new 1-cleaner job is requested for Tuesday, **Then** a free cleaner is chosen over that one, and no cleaner ends up with two jobs less than 1 hour apart.
3. **Given** a job longer than a workday (over 9 hours), **When** the back office books it, **Then** the request is refused with a clear message and nothing changes.
4. **Given** an existing cleaner, client or job, **When** the back office reads, updates or deletes it, **Then** the change is saved and visible on read, and an error (missing record, bad input) is shown without halting the app.

---

### User Story 2 - Cleaners work their day in the field (Priority: P1)

A cleaner opens the app and sees the jobs assigned to them today. They tap Arrive on arrival and Depart on completion; the elapsed time between the two taps is their time worked on the job.

**Why this priority**: Worked time is the basis of billing; without field time capture, invoices cannot be accurate. Together with booking it forms the minimum viable loop.

**Independent Test**: Assign jobs to a cleaner, perform Arrive/Depart taps, and verify the recorded per-cleaner worked time equals the difference between the taps, and that the cleaner's day view matches the back office's booking. Deliverable: trustworthy per-cleaner worked time.

**Acceptance Scenarios**:

1. **Given** a cleaner with two jobs today, **When** they view their day, **Then** both jobs appear with client, booked times and current state.
2. **Given** a job not yet started, **When** the cleaner taps Arrive, **Then** the arrival time is recorded; **When** they later tap Depart, **Then** the departure is recorded and worked time is the difference.
3. **Given** a job already departed, **When** the cleaner taps Depart again, **Then** the app shows an error and changes nothing.

---

### User Story 3 - Invoices are issued on completion and settled (Priority: P2)

When the last assigned cleaner departs a job, the job is complete and its invoice is issued at that moment, charging $45 per hour per cleaner on each cleaner's worked time, rounded to the nearest cent, and listing each cleaner's time. The back office records a single full payment, or sees any other amount refused, and sees which invoices are settled.

**Why this priority**: Invoice accuracy and timeliness is the second named pain, but it depends on booking (P1) and worked time (P1) existing first.

**Independent Test**: Complete a job with known per-cleaner times and verify an invoice appears automatically, itemized per cleaner, with the cent-exact total of worked hours x $45; pay it in full and verify it becomes settled; attempt a partial payment and see it refused.

**Acceptance Scenarios**:

1. **Given** a completed 2-cleaner job where cleaner A worked 4.0 h and cleaner B worked 3.5 h, **When** the second cleaner departs, **Then** an invoice is issued listing A: 4.0 h = $180.00, B: 3.5 h = $157.50, total $337.50.
2. **Given** an unsettled invoice, **When** the back office records a payment equal to its total, **Then** the invoice becomes settled; **When** the amount differs, **Then** it is refused with a message and the invoice stays unsettled.
3. **Given** a job whose first cleaner departed but whose second has not, **When** the back office looks for an invoice, **Then** none exists yet for that job.

---

### User Story 4 - Extensions and removals keep the schedule consistent (Priority: P2)

A cleaner who needs more time asks for it in 20-minute steps, which extends their schedule. If the extension leaves one of their later jobs starting less than 1 hour after the extended job's new end, that later job — and anything it in turn bumps — is booked again by the booking rule, starting no earlier than 1 hour after the extended end. Extensions may run past 17:00. Deleting a cleaner with future jobs rebooks those jobs by the booking rule; deleting a client cancels their future jobs. Issued invoices never change.

**Why this priority**: The field reality that jobs run long is what breaks schedules today; correctness here protects both P1 stories.

**Independent Test**: Extend a job repeatedly and verify the chain of rebookings respects the booking rule and the 1-hour spacing with no overlap anywhere afterwards; delete a cleaner with future jobs and a client with future jobs and verify rebooking/cancellation while issued invoices remain untouched.

**Acceptance Scenarios**:

1. **Given** a cleaner with a job ending 12:00 and a later job starting 12:30, **When** the cleaner takes one 20-minute extension (new end 12:20), **Then** the later job is rebooked at the earliest slot no earlier than 13:20 where enough cleaners are free.
2. **Given** a rebooking chain, **When** each bumped job is placed, **Then** the same booking rule (earliest slot on or after its minimum start, enough distinct free cleaners, inside 8:00–17:00 Mon–Fri) applies to every one.
3. **Given** a cleaner with future jobs, **When** the back office deletes the cleaner, **Then** those jobs are rebooked onto remaining cleaners per the booking rule.
4. **Given** a client with future jobs and an already-issued invoice, **When** the back office deletes the client, **Then** the future jobs are cancelled and the issued invoice is unchanged.

---

### User Story 5 - Utilization visibility (Priority: P3)

For each cleaner, the back office sees billable hours worked out of 8 per workday and out of 40 per week.

**Why this priority**: Reporting that supports the goal of maximizing utilization; valuable but not needed for the booking-to-cash loop.

**Independent Test**: After a period of booked work, verify each cleaner's day and week totals equal the summed worked times within the 8 h / 40 h frame.

**Acceptance Scenarios**:

1. **Given** a cleaner with recorded worked times in a week, **When** the back office views utilization, **Then** the day total and week total match the recorded worked time against 8 h and 40 h.

---

### Edge Cases

- Job longer than a workday (over 9 hours) at booking time -> refused with a message, nothing changes.
- No day on or after the requested day where enough distinct cleaners are free (e.g. a 3-cleaner job with fewer than 3 employable cleaners left) -> the request is refused with a clear message; nothing changes and no waiting queue is created.
- Requested day falls on a weekend -> the booking lands in the earliest slot on or after that day within working hours, i.e. from the following Monday at 8:00.
- Arrive or Depart tapped out of order, twice, or on a job not assigned to that cleaner -> error shown, nothing changes.
- Extension pushes a job's end past 17:00 -> allowed; jobs rebooked by that extension still land inside 8:00–17:00.
- Chains of extensions and rebookings of any length (each bumped job may bump the next) terminate when no later job violates the 1-hour spacing.
- Rebooking triggered by a cleaner deletion when too few cleaners remain for a 2- or 3-cleaner job -> that job cannot be rebooked; the situation is reported to the operator and the schedule is left consistent.
- Payment on an already-settled or unknown invoice -> refused, nothing changes.
- Deleting a cleaner or client with no future jobs -> plain deletion.
- Arrive and Depart at the same instant -> allowed; that cleaner's invoice line is $0.00.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the back office to create, read, update and delete cleaners, clients and jobs, and MUST show a clear error and change nothing when input is invalid or a record does not exist.
- **FR-002**: Every job MUST reference exactly one client, require 1, 2 or 3 cleaners, and carry an expected length; a job longer than one workday (over 9 hours) MUST be refused at booking.
- **FR-003**: System MUST assign the cleaners itself and book each job into the earliest slot, on or after the requested day, where enough distinct cleaners are free.
- **FR-004**: Every booked job MUST start and end within 8:00–17:00, Monday–Friday.
- **FR-005**: For any cleaner, no two of their scheduled jobs may have the second starting less than 1 hour after the first ends; booking, extension and rebooking MUST NOT create an overlap or a double booking.
- **FR-006**: Cleaners MUST be able to see the jobs assigned to them for the day.
- **FR-007**: Cleaners MUST be able to tap Arrive and Depart on each of their jobs, and worked time MUST equal the elapsed time between the two taps.
- **FR-008**: Cleaners MUST be able to request more time on their job in 20-minute steps, extending that cleaner's schedule; an extension MAY run past 17:00.
- **FR-009**: When an extension leaves one of the cleaner's later jobs starting less than 1 hour after the extended job's new end, system MUST rebook that later job by the booking rule with a minimum start of 1 hour after the extended job's new end, and MUST repeat the same for any job a rebooking bumps, until no violation remains.
- **FR-010**: When a cleaner with future jobs is deleted, those jobs MUST be rebooked by the booking rule; when a client is deleted, their future jobs MUST be cancelled; invoices already issued MUST NOT change.
- **FR-011**: System MUST mark a job complete when the last of its cleaners departs and MUST issue its invoice at that moment.
- **FR-012**: Every invoice MUST charge $45 per hour on each cleaner's worked time, rounded to the nearest cent, and MUST list each cleaner's time.
- **FR-013**: System MUST settle an invoice only on a single payment equal to its full total; a payment of any other amount MUST be refused.
- **FR-014**: Back office MUST be able to see which invoices are settled and which are not.
- **FR-015**: System MUST report, for each cleaner, billable hours worked out of 8 per workday and out of 40 per week.
- **FR-016**: On any error (bad input, a record that doesn't exist, a request that can't be met) the app MUST NOT stop; it MUST show the error to the person using it, change nothing, and carry on working.

### Key Entities

- **Cleaner**: A person who performs jobs (12 in the business). Attributes: identity, name, schedule of assigned jobs.
- **Client**: The household that receives cleaning. Attributes: identity, name, its jobs.
- **Job**: One cleaning visit for one client. Attributes: client, requested day, expected length, cleaners required (1–3), assigned cleaners, booked start/end, state (scheduled / in progress / complete / cancelled), per-cleaner arrival and departure times and worked time.
- **Invoice**: Issued the moment its job completes. Attributes: job reference, issue moment, per-cleaner lines (worked time, amount at $45/h to the nearest cent), total, settlement state, payment amount and date.
- **Utilization report**: Per cleaner, billable hours worked against the 8 h workday and the 40 h week.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of create/read/update/delete operations on cleaners, clients and jobs complete without error or app stoppage across a scripted workload with the full team (12 cleaners, 2 back-office staff) and a realistic job mix (averaging ~4.14 h, standard deviation ~1.75 h).
- **SC-002**: An audit of all bookings, extensions and rebookings finds zero cases of a cleaner holding two jobs where the second starts less than 1 hour after the first ends, and zero scheduled jobs (extensions past 17:00 excepted, per that rule) outside 8:00–17:00 Monday–Friday.
- **SC-003**: 100% of invoices are issued at the moment their job's last cleaner departs, and each invoice's total equals the sum of each cleaner's worked hours x $45 rounded to the nearest cent, matching the recorded Arrive/Depart times.
- **SC-004**: Every rebooking (delete-cleaner rebooking and 20-minute extension bumps) places each moved job in the earliest slot allowed by the booking rule from its minimum start, with no unresolved conflicts remaining.
- **SC-005**: Back office can determine the settlement state of any invoice: 100% of non-full payments are refused and every full-amount payment settles its invoice.
- **SC-006**: Utilization figures shown to the back office equal the recorded worked time per cleaner against the 8 h/day and 40 h/week frames.
- **SC-007**: Every error condition exercised in testing displays a message to the person using the app and leaves the records exactly as they were before the failed operation.

## Assumptions

- Two expressions of one solution follow the same rules — a local web page served by Python for the back office, and a logic-only mobile component for cleaners with no user interface; each keeps its data in a local file and the two are not connected. "In sync" therefore means consistent rules and consistent records, not live data exchange. (Scope note from the problem statement, not a design instruction for later phases.)
- A workday is 8:00–17:00 Monday–Friday, so 9 hours is the maximum job length; no holiday or vacation calendars exist. "Week" means the calendar week containing the job's day.
- No feasible slot (e.g. not enough cleaners left for the required headcount) means the request is refused with an error; there is no waiting queue — the problem statement offers no basis for one.
- All cleaners are interchangeable: any free cleaners will do; no skills, ratings, territories or preferred pairings exist.
- Times are local, minute-granular; the 20-minute step and the 1-hour spacing are exact rules (a job starting exactly 1 hour after another ends is legal).
- Rounding to the nearest cent is applied to each cleaner's line ($45/h x worked hours); the invoice total is the sum of the rounded lines.
- Extensions may push a cleaner beyond 8 billed hours in a day; the 8 h/40 h figures frame the utilization target, not a hard cap.
- No sign-in, payroll, recurring appointments, maps, travel time, notifications, email or payment processing (declared out of scope by the problem statement).
- All data is synthetic; no privacy or compliance regime beyond error-free operation is assumed.
