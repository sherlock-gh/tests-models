# Feature Specification: Cleaning Scheduling and Billing

**Feature Branch**: `main`

**Created**: 2026-11-11

**Status**: Draft

**Input**: House-cleaning scheduling and billing problem in `problem.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintain records and book work (Priority: P1)

Back-office staff maintain cleaners, clients and jobs, and book jobs into the earliest eligible slot with enough available cleaners. This gives the business a reliable schedule without double bookings.

**Why this priority**: A valid schedule is the foundation for field work and billing.

**Independent Test**: Create and retrieve records, book jobs with varying staffing and durations, update and delete records, and inspect the resulting schedule.

**Acceptance Scenarios**:

1. **Given** a client and enough cleaners with availability, **When** staff book a job requiring one to three cleaners, **Then** it is placed in the earliest eligible slot on or after the requested day and assigned enough free cleaners.
2. **Given** a cleaner has a job ending at 12:00, **When** another job is booked for that cleaner, **Then** it starts no earlier than 13:00 and remains within working hours.
3. **Given** a job longer than nine hours or otherwise invalid input, **When** staff attempt to save it, **Then** they see an error and no records or schedules change.
4. **Given** existing cleaner, client and job records, **When** staff read, update or delete them, **Then** the requested change is reflected, subject to the removal and history rules below.

### User Story 2 - Record work and handle extensions (Priority: P1)

A cleaner views their jobs for the day, records arrival and departure, and requests more time when needed. Later affected jobs are rebooked so schedules remain conflict-free.

**Why this priority**: Field progress and accurate time are necessary for both scheduling and invoices.

**Independent Test**: View an assigned day, record arrival and departure, and extend a job that triggers a chain of rebookings.

**Acceptance Scenarios**:

1. **Given** a cleaner is assigned to a job today, **When** they view their day and tap Arrive and later Depart, **Then** the job appears and their elapsed time is recorded.
2. **Given** a job has a later job less than one hour after its extended end for an assigned cleaner, **When** the cleaner requests a 20-minute increment, **Then** the later job is rebooked no earlier than one hour after that end using the booking rule; any jobs it bumps are likewise rebooked.
3. **Given** an extension ends after 17:00, **When** it is accepted, **Then** the extended job may finish after 17:00 and affected later jobs are rebooked under normal booking hours.
4. **Given** an invalid time action or an extension that cannot be accommodated, **When** it is requested, **Then** an error is shown and all records and schedules remain unchanged.

### User Story 3 - Issue and settle invoices (Priority: P1)

When the last assigned cleaner departs, the business issues an invoice based on each cleaner's actual time. Back-office staff record full payment and see whether invoices are settled.

**Why this priority**: Timely, accurate invoices and payment status are core business outcomes.

**Independent Test**: Complete a multi-cleaner job with different recorded times, inspect the issued invoice, and attempt full and partial payments.

**Acceptance Scenarios**:

1. **Given** all but one assigned cleaner have departed, **When** the last cleaner departs, **Then** an invoice is issued immediately showing each cleaner's time and the total at $45 per cleaner-hour rounded to the nearest cent.
2. **Given** an unpaid invoice, **When** staff record a payment equal to its total, **Then** it is marked settled; any other amount is refused without changing it.
3. **Given** an issued invoice, **When** its client is deleted, **Then** the invoice and its details remain unchanged and its settlement status remains visible.

### User Story 4 - Recover schedules after removals and review utilization (Priority: P2)

Back-office staff remove cleaners or clients when necessary and review cleaner utilization against daily and weekly targets.

**Why this priority**: These actions keep future schedules usable and expose how much billable work each cleaner performs.

**Independent Test**: Delete a cleaner and a client with future jobs, inspect the resulting schedule and invoices, and compare recorded billable time to daily and weekly denominators.

**Acceptance Scenarios**:

1. **Given** a cleaner has future jobs, **When** staff delete that cleaner, **Then** those jobs are rebooked using the booking rule with sufficient remaining cleaners, or the deletion fails without changes if it cannot be satisfied.
2. **Given** a client has future jobs and issued invoices, **When** staff delete that client, **Then** the future jobs are cancelled and issued invoices remain unchanged.
3. **Given** a cleaner has billable time in a workday and week, **When** staff view utilization, **Then** they see billable hours against eight hours for that day and 40 hours for that week.

### Edge Cases

- A job ending exactly at 17:00 is eligible; a subsequent job exactly one hour after a previous end is not an overlap.
- A job cannot fit across working days; weekends are skipped. A job exceeding nine hours is refused.
- If fewer than the required number of cleaners exist, or a rebooking cannot be completed, the whole requested change fails without partial changes.
- Arrival must precede departure for each assigned cleaner; repeated or out-of-order actions are rejected without changing recorded time.
- Updating a scheduled job must preserve the booking rules; changing an already completed job must not alter an issued invoice.
- An extension can move several later jobs, including multi-cleaner jobs; every affected assignment must remain conflict-free.
- Zero or negative durations, unsupported staffing counts, missing records and payments unequal to the invoice total are rejected without changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Back-office staff MUST be able to create, view, update and delete cleaner, client and job records, subject to the scheduling and historical rules in this specification.
- **FR-002**: Each job MUST identify one client, a requested day, an expected duration and a requirement for one, two or three cleaners.
- **FR-003**: The system MUST assign any sufficiently available cleaners and book each job at the earliest available start on or after its requested day, subject to working hours and the one-hour separation rule.
- **FR-004**: Normal bookings and rebookings MUST start and end between 08:00 and 17:00 Monday through Friday, within a single workday; durations longer than nine hours MUST be refused.
- **FR-005**: For every cleaner, a later job MUST start at least one hour after their earlier job ends; bookings, updates, extensions and rebookings MUST leave no double bookings or overlaps.
- **FR-006**: Each cleaner MUST be able to view their assigned jobs for a chosen day and record arrival and departure for each job. Their time worked MUST equal the elapsed time between their own arrival and departure.
- **FR-007**: A cleaner MUST be able to request additional time in 20-minute increments for an active job. The scheduled end MUST be extended accordingly, even beyond 17:00 when necessary.
- **FR-008**: When an extension leaves a later job assigned to any cleaner on the extended job less than one hour after its new end, that later job MUST be rebooked under FR-003 and FR-004 no earlier than one hour after the extended end. Jobs displaced by rebooking MUST be rebooked in the same way until the schedule satisfies FR-005.
- **FR-009**: Deleting a cleaner MUST rebook their future jobs under the booking rule using the remaining cleaners; deleting a client MUST cancel that client's future jobs. Issued invoices MUST remain unchanged by either deletion.
- **FR-010**: A job MUST be completed when its last assigned cleaner departs, and its invoice MUST be issued at that moment.
- **FR-011**: Each invoice MUST list each cleaner's time worked and charge $45 per cleaner-hour for actual time worked, with the total rounded to the nearest cent.
- **FR-012**: Back-office staff MUST be able to record one payment equal to an invoice's full total and view whether each invoice is settled or unsettled. Other payment amounts MUST be refused.
- **FR-013**: Back-office staff MUST be able to view each cleaner's billable hours for a workday out of eight hours and for a week out of 40 hours.
- **FR-014**: Invalid input, missing records and requests that cannot be fulfilled MUST produce a visible error, leave all data unchanged, and allow the user to continue working.
- **FR-015**: The back-office and cleaner expressions MUST each follow these same business rules and retain their own data locally; sharing or synchronizing data between them is outside this feature.

### Key Entities *(include if feature involves data)*

- **Cleaner**: A person available for jobs, with assignments, recorded work time and utilization.
- **Client**: The recipient of cleaning jobs and associated invoices.
- **Job**: Work for one client, with requested day, expected duration, staffing requirement, scheduled interval, assignments and status.
- **Work record**: One assigned cleaner's arrival, departure and elapsed time for a job.
- **Invoice**: An issued, preserved account of a completed job, its cleaners' time, total charge and settlement status.
- **Payment**: A single full settlement of an invoice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance testing, 100% of valid create, read, update and delete operations on cleaners, clients and jobs complete correctly, subject to the stated rules.
- **SC-002**: In acceptance tests covering bookings, extensions, chained rebookings and removals, 100% of resulting schedules have no double booking or less than one hour between consecutive jobs for a cleaner.
- **SC-003**: In acceptance tests, 100% of completed jobs receive an invoice at the last departure, with every cleaner's time and the correctly rounded total.
- **SC-004**: In acceptance tests, 100% of full payments settle their invoices, all other amounts are refused, and staff can identify every invoice's settlement status.
- **SC-005**: In acceptance tests, 100% of invalid or unsatisfiable requests show an error, leave data unchanged and permit a subsequent valid action.
- **SC-006**: In a representative task test, at least 90% of back-office and cleaner participants can complete their respective primary booking or time-recording task without assistance.

## Assumptions

- The business starts with approximately 12 cleaners and two back-office staff; staffing can change through record maintenance.
- All data is synthetic. The two independent expressions have local data, no outside services or shared synchronization: the back office uses a locally served desktop web page, and the cleaner expression supplies mobile app logic without a user interface.
- A future job is one that has not started and whose scheduled start is after the time of the removal. In-progress work is retained to completion; historical records needed for invoices are retained.
- A scheduled job update that affects availability is treated as a fresh booking, starting no earlier than its requested day. Completed jobs and issued invoices retain their historical billing details.
- Ties for the earliest start may be resolved using any eligible cleaners. Time is measured using actual elapsed time; the invoice total is rounded once to the nearest cent.
- Billable hours are recorded hours on completed, invoiced jobs, attributed to the day on which they were worked; a week is Monday through Sunday. Daily and weekly utilization may exceed their denominators.
- Requests are atomic, including cascading rebookings. The stated average duration of 4.14 hours and standard deviation of 1.75 hours describe expected demand, not booking limits.
- Payroll, recurring appointments, maps, travel time, notifications, accounts and sign-in, email, payment processing, and connection between the two expressions are excluded.
