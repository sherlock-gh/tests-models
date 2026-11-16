# Interface contracts

These are behavioral contracts for the locally served back-office web page and the cleaner-facing Swift package. They describe capabilities and outcomes, not a required HTTP route, Swift signature, or shared file format. Each expression keeps an independent local store. See [data model](../data-model.md) for fields, validation, lifecycle, and atomicity.

## Back-office web page

The page must allow staff to:

| Action | Input | Successful result |
| --- | --- | --- |
| Maintain cleaners and clients | Create, read, update, or delete an identified record; name for creation or update | Current records are displayed; deletions apply the future-job and historical rules. |
| Maintain jobs | Client, requested day, expected duration and required cleaner count; job ID for read, update or delete | Show the saved job, scheduled interval, assigned cleaners and status. Create and availability-affecting update use the earliest eligible booking rule. |
| Review invoices | Optional selection of an invoice | Show issued invoice details, each cleaner's time, total and settled/unsettled status, including after a client or cleaner is deleted. |
| Record payment | Invoice ID and amount | Accept exactly one full payment and show the invoice as settled. |
| Review utilization | Cleaner and selected workday or week | Show billable hours and the applicable eight- or 40-hour denominator. |

Every failed action must visibly explain the error, leave all data unchanged, and permit a later valid action. Invalid dates, duration or staffing; missing records; unavailable bookings; and non-full or repeated payments are failures. A delete or edit cannot rewrite an issued invoice.

## Cleaner package

The package exposes callable operations for a host to invoke without a UI:

| Operation | Input | Successful result |
| --- | --- | --- |
| List assigned jobs | Cleaner ID and chosen day | Jobs assigned to that cleaner on the selected day, including scheduled interval, client and status. |
| Arrive | Cleaner ID and assigned job ID | Record one arrival on that assignment and return the updated work state. |
| Depart | Cleaner ID and assigned job ID | Record one departure after arrival and return elapsed time. The last assigned cleaner's departure also completes the job and issues its invoice atomically. |
| Extend | Cleaner ID, active assigned job ID and positive count of 20-minute increments | Extend the end and return the updated schedule after all necessary rebookings. The extended job may end after 17:00. |

Invalid identifiers, unassigned cleaners, repeated or out-of-order time actions, invalid increments, or an unsatisfiable cascade return a usable error without changing any data. Operations that read the current time must use a consistent clock; elapsed time is measured between actual arrival and departure instants.

## Cross-expression behavior

Both expressions implement the same booking, rebooking, billing and failure rules even though their files and interfaces are independent. Booking finds the earliest eligible start on or after the requested day, requires enough cleaners, and preserves one hour between consecutive jobs for every cleaner. An extension rebooks each affected later job no earlier than one hour after the extended end and propagates displacement until the schedule is valid. Mutations including cascades are all-or-nothing; no synchronization or external service is part of this contract.
