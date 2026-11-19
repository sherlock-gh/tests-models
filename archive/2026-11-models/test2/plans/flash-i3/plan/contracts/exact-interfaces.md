# Contract: Exact interfaces (both apps)

Added to the plan so that both apps can be checked by program. [desktop-api.md](desktop-api.md), [cleaner-api.md](cleaner-api.md), [rules-core.md](rules-core.md) and [../data-model.md](../data-model.md) stay the contract; this file fixes only what they leave open. Where they differ, this file wins.

## Both apps

- **Taps of a split job:** each assigned cleaner taps Arrive and Depart once on each part (data-model.md: two taps per cleaner per part worked). A cleaner's taps alternate Arrive, Depart; a cleaner who has departed as many times as the job has parts has finished it. The job completes, and its invoice issues, when every assigned cleaner has finished it; each line's minutes are the sum over that cleaner's Arrive–Depart pairs.
- **The day list** holds the cleaner's non-cancelled jobs that have a part starting on that day, ordered by that part's start.
- **More time** adds 20 minutes to the end of the part the cleaner is working (the part their open Arrive is on).
- **Times** are local: the host's time zone in the desktop app, the injected `timeZone` in the package.

## Desktop app (Python, `desktop/`)

- **Starting it:** `python -m desktop.server` from the repository root, or `.venv/bin/python -m desktop.server` when the repository has a `.venv`. Environment: `PORT` (the port on 127.0.0.1) and `CLEANING_DATA` (the path of its data file). It serves until stopped.
- **Requests and answers** are JSON. A success answers `200` (`201` for a create) with the body desktop-api.md gives. An error answers `400`, or `404` for an unknown record, with `{"error": "<message>"}`, and the data file is unchanged.
- **Taps** take an optional `"at"` in the body, a local `"YYYY-MM-DDTHH:MM"`: the tap's instant, the current time when left out.
- **Job:** `parts` are `{"start_day": "YYYY-MM-DD", "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "duration_min"}`; `invoice_id` is `null` until the invoice issues; `status` is `booked`, `in_progress`, `complete` or `cancelled`; `taps` are `{"cleaner_id", "kind": "arrive" | "depart", "instant": "YYYY-MM-DDTHH:MM"}`.
- **Depart** answers the Job, with an `"invoice"` key holding the Invoice when this Depart issued it. **More time** answers the Job with a `"rebooked"` key: a list of `{"job_id", "parts"}`, empty when nothing moved.
- **Invoice:** `issued_at` is the last Depart's instant; `amount_str` and `total_str` are dollars with two decimals after a `$` (`"$157.50"`).
- **Utilization:** `hours_worked` is a number (minutes / 60); every cleaner on file has an entry.

## Cleaner package (Swift, `CleaningKit/`)

Library and module `CleaningKit`, test target `CleaningKitTests` in `Tests/CleaningKitTests`, the `CleaningStore` API in cleaner-api.md, with these exact forms:

- `public struct CleaningError: Error { public let message: String }`
- `public func updateInvoice(id: Int, totalCents: Int) throws -> Invoice` and `public func deleteInvoice(id: Int) throws`: both always throw.
- `public func save()` is not needed: every successful call writes the file; a new `CleaningStore` on the same file sees it.
- Days (`DateComponents`) carry `year`, `month` and `day`.

Its public records (structs, `public` properties):

| Record | Properties |
|---|---|
| Cleaner, Client | `id: Int`, `name: String` |
| Job | `id: Int`, `clientId: Int`, `cleanersNeeded: Int`, `expectedLengthMinutes: Int`, `requestedDay: DateComponents`, `cleanerIds: [Int]`, `status: JobStatus`, `parts: [JobPart]`, `invoiceId: Int?`, `invoice: Invoice?` (set on the Job a Depart returns when that Depart issued it), `taps: [Tap]` |
| JobStatus | `enum JobStatus: String { case booked, inProgress = "in_progress", complete, cancelled }` |
| JobPart | `start: Date`, `end: Date`, `durationMinutes: Int` |
| Tap | `cleanerId: Int`, `kind: TapKind` (`enum TapKind: String { case arrive, depart }`), `instant: Date` |
| Invoice | `id: Int`, `jobId: Int`, `issuedAt: Date`, `lines: [InvoiceLine]`, `totalCents: Int`, `settled: Bool` |
| InvoiceLine | `cleanerId: Int`, `minutesWorked: Int`, `cents: Int` |
| RebookedJob | `jobId: Int`, `parts: [JobPart]` |
| MoreTimeOutcome | `job: Job`, `rebooked: [RebookedJob]` |
| UtilizationEntry | `cleanerId: Int`, `name: String`, `hoursWorked: Double`, `hoursOf: Int` |
