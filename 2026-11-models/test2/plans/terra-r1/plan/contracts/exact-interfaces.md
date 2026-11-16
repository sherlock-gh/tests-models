# Contract: Exact interfaces (both apps)

Added to the approved plan so the interfaces are exact. [interfaces.md](interfaces.md) and [data-model.md](../data-model.md) describe the behaviour; this file fixes the names, fields, routes and signatures. Where they differ, this file wins.

## Time

Dates are `YYYY-MM-DD`; instants are business-local `YYYY-MM-DDTHH:MM:SS`. Scheduled times are whole minutes from local midnight. The injectable clock (tasks T005, T006) gives "now" as such an instant; arrival, departure, removals ("future" jobs) and invoice issue read it.

## Records (the same fields in both apps)

| Record | Fields |
|---|---|
| Cleaner | `id` (int), `name` (string) |
| Client | `id` (int), `name` (string) |
| WorkRecord | `cleanerId` (int), `arrivedAt`, `departedAt` (instant or null), `elapsedSeconds` (int or null) |
| Job | `id`, `clientId`, `cleanersNeeded`, `durationMinutes` (ints), `requestedDate`, `date` (dates), `startMinute`, `endMinute` (ints), `cleanerIds` (ints, ascending), `status` (`scheduled`, `in_progress`, `completed`, `cancelled`), `work` (one WorkRecord per assigned cleaner) |
| InvoiceLine | `cleanerId` (int), `cleanerName` (string), `elapsedSeconds` (int) |
| Invoice | `id`, `jobId` (ints), `issuedAt` (instant), `clientName` (string), `lines`, `totalCents` (int), `settled` (bool) |
| Utilization | `cleanerId` (int), `date` (date), `daySeconds`, `weekSeconds` (ints) |

A deleted cleaner or client is no longer returned by get or list. When several sets of cleaners are free for the earliest start, the job gets those with the lowest ids. The invoice total is the lines' elapsed seconds summed, at $45 an hour, rounded once to the nearest cent, half up: `(totalSeconds × 5 + 2) // 4` cents.

## Desktop (Python)

- Started with `python3 backoffice/server.py --data PATH --port N`, run from the repository root; it serves until stopped.
- The clock: a request with header `X-Clock: <instant>` runs at that instant; without it, at the system time.
- A single record is a JSON object; a list is a JSON array. Errors: `{"error": {"code", "message"}}`, code `invalid_input` (400), `not_found` (404), or `unschedulable`, `invalid_state`, `payment_mismatch` (409).

| Method & path | Body or query | Returns |
|---|---|---|
| GET/POST `/api/cleaners`, GET/PUT/DELETE `/api/cleaners/{id}` | `{"name"}` | Cleaner(s); DELETE: 204 |
| GET/POST `/api/clients`, GET/PUT/DELETE `/api/clients/{id}` | `{"name"}` | Client(s); DELETE: 204 |
| GET/POST `/api/jobs`, GET/PUT/DELETE `/api/jobs/{id}` | `{"clientId", "cleanersNeeded", "durationMinutes", "requestedDate"}` (PUT: fields left out are unchanged) | Job(s); DELETE: 204 |
| GET `/api/cleaners/{id}/jobs?date=` | | the cleaner's jobs that day, by start |
| POST `/api/jobs/{id}/arrive`, `/api/jobs/{id}/depart` | `{"cleanerId"}` | Job |
| POST `/api/jobs/{id}/extend` | `{"cleanerId", "increments"}` (each 20 minutes) | Job |
| GET `/api/invoices?settled=true\|false`, GET `/api/invoices/{id}` | | Invoice(s) |
| POST `/api/invoices/{id}/pay` | `{"amountCents"}` | Invoice |
| GET `/api/utilization?cleanerId=&date=` | | Utilization: the day of `date` and its Monday–Sunday week |
| GET `/` | | the back-office page |

## Mobile (Swift)

Package `mobile/`, library and module `CleaningLogic`, test target `CleaningLogicTests`. The records above are public `Codable, Equatable` structs with those property names (optional where "or null"; `status` a `String`).

```swift
public struct CleaningError: Error, Equatable { public let code: String; public let message: String }

public final class CleaningService {
    public init(storeURL: URL, clock: @escaping () -> String) throws   // missing file: empty data
    public convenience init(storeURL: URL) throws                       // the system clock
    public func createCleaner(name: String) throws -> Cleaner
    public func updateCleaner(id: Int, name: String) throws -> Cleaner
    public func deleteCleaner(id: Int) throws
    public func getCleaner(id: Int) throws -> Cleaner
    public func listCleaners() -> [Cleaner]
    public func createClient(name: String) throws -> Client
    public func updateClient(id: Int, name: String) throws -> Client
    public func deleteClient(id: Int) throws
    public func getClient(id: Int) throws -> Client
    public func listClients() -> [Client]
    public func bookJob(clientId: Int, cleanersNeeded: Int, durationMinutes: Int, requestedDate: String) throws -> Job
    public func updateJob(id: Int, clientId: Int?, cleanersNeeded: Int?, durationMinutes: Int?, requestedDate: String?) throws -> Job
    public func deleteJob(id: Int) throws
    public func getJob(id: Int) throws -> Job
    public func listJobs() -> [Job]
    public func assignedJobs(cleanerId: Int, date: String) throws -> [Job]
    public func arrive(jobId: Int, cleanerId: Int) throws -> Job
    public func depart(jobId: Int, cleanerId: Int) throws -> Job
    public func extend(jobId: Int, cleanerId: Int, increments: Int) throws -> Job
    public func listInvoices(settled: Bool?) -> [Invoice]
    public func getInvoice(id: Int) throws -> Invoice
    public func payInvoice(id: Int, amountCents: Int) throws -> Invoice
    public func utilization(cleanerId: Int, date: String) throws -> Utilization
}
```

Every successful change is saved to `storeURL` before the method returns; a new `CleaningService` on the same file sees it.
