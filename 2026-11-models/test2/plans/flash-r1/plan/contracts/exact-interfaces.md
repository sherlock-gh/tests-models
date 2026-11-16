# Contract: Exact interfaces (both apps)

Added to the approved plan so that its pages and API can be checked by program. [backoffice-web.md](backoffice-web.md), [cleaner-logic-swift.md](cleaner-logic-swift.md) and [../data-model.md](../data-model.md) stay the contract; this file fixes only what they leave open. Where they differ, this file wins.

## Back office (Python, `webapp/`)

- **Starting it:** `python3 webapp/app.py` from the repository root, or `.venv/bin/python webapp/app.py` when the repository has a `.venv`. Environment: `PORT` (the port on 127.0.0.1) and `STORE` (the path of its JSON file; default `webapp/data/store.json`). It serves until stopped.
- **Machine-readable answers:** every route in backoffice-web.md also answers in JSON when the request has the header `Accept: application/json`. Forms are posted as in the contract (form-encoded fields); with that header, a successful action answers `200` with the record it created or changed (a delete: `{}`), instead of redirecting; a page answers with its records.
- **Errors**, with that header: `200` and `{"error": {"code", "message"}}`, as the contract's error rule says, with `code` one of `not_found`, `invalid_input`, `job_too_long`, `no_feasible_slot`, `tap_out_of_order`, `wrong_cleaner`, `payment_amount_mismatch`, `already_settled`, `not_enough_cleaners` (the Swift `CleaningError` cases, in snake case).
- **Records in JSON** use the data model's field names: Cleaner and Client `{"id", "name"}`; Job `{"id", "client_id", "requested_day", "expected_length_min", "cleaners_required", "booked_start", "booked_end", "state", "assignments": [{"cleaner_id", "arrival", "departure", "worked_min"}], "invoice_id"}`; Invoice `{"id", "job_id", "issued_at", "lines": [{"cleaner_id", "worked_min", "amount"}], "total", "settled", "payment_amount", "payment_date"}`. Dates are `YYYY-MM-DD`; datetimes are local `YYYY-MM-DDTHH:MM`; money is a string with two decimals (`"367.50"`); `state` is `scheduled`, `in_progress`, `complete` or `cancelled`.
- **Form fields:** cleaners and clients `name`; `POST /jobs/book` and `POST /jobs/<id>` `client_id`, `cleaners_required`, `hours` (a decimal number of hours, converted to whole minutes), `requested_day`; taps `at` (a local datetime; the current time when left out); `POST /invoices/<id>/pay` `amount`.
- **Lists:** `GET /cleaners`, `/clients`, `/jobs` and `/invoices` answer a JSON array of records. `GET /field/<cleaner_id>/today` takes `?day=YYYY-MM-DD` (default today) and answers the cleaner's jobs that day, by start. `GET /utilization?day=` answers one object a cleaner: `{"cleaner_id", "day_worked_min", "week_worked_min"}`.

## Cleaner package (Swift, `CleanerApp/`)

Library and module `CleaningLogic`, test target `CleaningLogicTests`, the `Store` API in cleaner-logic-swift.md, plus `public func job(id: Int) -> Job?`. Its public records have these properties (each `var` where an update takes the record):

| Record | Properties |
|---|---|
| Cleaner, Client | `id: Int`, `name: String` |
| Job | `id: Int`, `clientID: Int`, `requestedDay: Date`, `expectedLengthMinutes: Int`, `cleanersRequired: Int`, `bookedStart: Date`, `bookedEnd: Date`, `state: String` (as above), `assignments: [JobAssignment]`, `invoiceID: Int?` |
| JobAssignment | `cleanerID: Int`, `arrival: Date?`, `departure: Date?`, `workedMinutes: Int?` |
| Invoice | `id: Int`, `jobID: Int`, `issuedAt: Date`, `lines: [InvoiceLine]`, `total: Decimal`, `settled: Bool`, `paymentAmount: Decimal?`, `paymentDate: Date?` |
| InvoiceLine | `cleanerID: Int`, `workedMinutes: Int`, `amount: Decimal` |
| UtilizationReport | `cleanerID: Int`, `dayWorkedMinutes: Int`, `weekWorkedMinutes: Int` |

Times are local: dates and times use `Calendar.current` and `TimeZone.current`. A change reaches the file on `save()`; a new `Store` on the same file sees what was saved.
