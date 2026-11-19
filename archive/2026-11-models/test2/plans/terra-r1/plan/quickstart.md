# Quickstart validation

These commands describe the planned implementation; the application and test suites do not exist yet. Run from the repository root once implemented. Use synthetic data and isolated temporary files for each expression; neither expression shares or synchronizes its data.

## Prerequisites and setup

Install Python 3.14 and Swift 6.1 with Swift Package Manager. No external services or packages are required. The Python and Swift test fixtures must each create and remove their own temporary local data file.

## Automated checks

```sh
python3 -m unittest discover -s backoffice/tests
swift test --package-path mobile
```

Both suites should pass independent instances of these scenarios:

1. Create a client and cleaners, book one-, two- and three-cleaner jobs, and verify the earliest weekday interval, 08:00–17:00 bounds, and one-hour gaps, including equality boundaries and weekend rollover.
2. Record each assigned cleaner's arrival and departure; on the last departure verify an invoice with each elapsed time and a total at $45 per cleaner-hour rounded once to cents. Verify only a single exact full payment settles it.
3. Extend an active job in 20-minute increments, including past 17:00, and check cascading multi-cleaner rebookings and their one-hour separation. Remove a cleaner and verify future jobs rebook; remove a client and verify future jobs cancel while invoices remain unchanged.
4. Compare completed billable time with daily eight-hour and Monday–Sunday 40-hour denominators. Exercise invalid values, out-of-order time actions, missing records and unsatisfiable rebookings; verify the entire persisted state remains unchanged and a later valid action succeeds.

## Back-office walkthrough

Start the planned local server with `python3 backoffice/server.py`, open the local address it prints, and use its forms to create records, book a job, inspect the schedule and invoice, and record a full payment. Confirm errors are visible without terminating the application. The Swift package's corresponding cleaner flows are exercised through `swift test`; it intentionally has no UI.

See [data-model.md](data-model.md) and [contracts/](contracts/) for the data and interface rules to validate.
