# Problem: scheduling and billing for a house-cleaning business

The business is fictitious and every piece of data in this work is synthetic.

## Who is affected

A house-cleaning business with 12 cleaners and 2 back-office staff. The cleaners work at clients' homes. The back office books the jobs, invoices the clients and tracks payment.

## What to build

Two apps that follow the same rules, each keeping its data in its own local file; the two are not connected.

- **Desktop, for the back office:** a local web page served by Python.
- **Mobile, for cleaners:** a Swift package holding the app's logic, with no user interface.

## What hurts today

Appointments are not kept in sync between the field and the back office. Cleaners get double-booked, or booked into jobs that overlap. Their days have unnecessarily large gaps between appointments. Invoices are inaccurate, and they go out late.

## Goals

Maximize cleaner utilization through effective appointment management and communication between the field and the back office. Concretely:

- **Records.** Back office can create, read, update and delete cleaners, clients and jobs.
- **Booking.** A job is for one client, needs 1, 2 or 3 cleaners, and has an expected length. Jobs average about 4.14 hours, with a standard deviation of about 1.75 hours. The system assigns the cleaners itself. It books the job into the earliest slot, on or after the requested day, where enough cleaners are free. Any free cleaners will do. Jobs start on the quarter hour (8:00, 8:15, 8:30 …). The search looks up to 90 days past the requested day; if there is no slot by then, the booking is refused with a message.
- **Working hours.** A workday runs from 8:00 to 17:00, Monday to Friday. A booked job starts and ends within those hours. A job longer than 8 hours is split across consecutive workdays, the same cleaners on every part: as many 8-hour parts as it needs, then the rest, each part booked by the booking rule. Times are the business's local time, and the calendar's clock changes apply. There are no holidays.
- **No overlaps.** Two jobs for the same cleaner overlap when the second starts less than 1 hour after the first ends. No booking may create an overlap or a double booking.
- **In the field.** A cleaner sees their jobs for the day. They tap Arrive when they get to a job and Depart when they leave. The time between the two taps is that cleaner's time worked on the job.
- **More time.** A cleaner who has arrived on a job in progress can ask for more time on it in 20-minute steps, as many as needed, which extends their schedule. When that leaves one of their later jobs less than 1 hour after the extended job ends, the later job is booked again by the booking rule, starting no earlier than 1 hour after the extended job's new end. A job that this bumps is booked again the same way. Extensions may run past 17:00.
- **Removals.** A future job is one nobody has tapped Arrive on yet. When a cleaner with future jobs is deleted, those jobs are booked again by the booking rule, with any free cleaners. When a client is deleted, their future jobs are cancelled. A job whose invoice has been issued can't be deleted. Issued invoices never change and are never deleted.
- **Invoices.** A job is complete when the last of its cleaners departs. Its invoice is issued at that moment. It charges $45 per hour for each cleaner, on each cleaner's time worked, and lists each cleaner's time. Taps are recorded to the minute. Each cleaner's line is rounded to the nearest cent, half a cent up; the invoice's total is the sum of its lines.
- **Settlement.** An invoice is paid in full in one payment. A payment of any other amount is refused. Back office can see which invoices are settled and which are not.
- **Utilization.** For each cleaner: billable hours worked out of 8 per workday, and out of 40 per week (Monday to Sunday). Work that runs past midnight counts on each day for the part worked that day. Hours may exceed 8 or 40.
- **No other rules.** Nothing beyond what is written here: no booking notice, payment due dates or similar rules of your own.

## Examples at the boundaries

- A cleaner's job ends at 12:00: their next job may start at 13:00, not 12:45.
- A cleaner's job ends at 12:10: their next job may start at 13:15, the first quarter hour at least an hour later.
- A job requested for a Saturday is booked from Monday at 8:00.
- An 8-hour job fits one day (8:00 to 16:00). A 10-hour job is two parts: 8 hours on one workday, 2 hours on the next, the same cleaners on both.
- A cleaner who works 3 hours 30 minutes is charged $157.50.
- A cleaner who works from 22:00 to 2:00 has 2 hours on each of the two days.
- A request with no slot in the 90 days after the requested day is refused with a message, and nothing changes.

## Out of scope

Anything beyond scheduling, tracking time and billing: payroll, recurring appointments, maps, travel time, notifications, accounts and sign-in, email, and payment processing. Connecting the two apps is also out of scope.

## How success is judged

- Every create, read, update and delete on cleaners, clients and jobs works without error.
- No booking, extension or rebooking ever leaves a double booking or an overlap.
- When an error occurs (bad input, a record that doesn't exist, a request that can't be met), the app doesn't crash. It shows the error to the person using it, changes nothing, and carries on working.
- Every invoice is complete and accurate, and is issued when its job completes.
- Back office can track which invoices are settled.

## Known limits

- **No services.** No network services, accounts or outside data.
- **Synthetic data.** All data is synthetic.
