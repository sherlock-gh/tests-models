# Contract: Exact interfaces (both apps)

Added to the approved plan so the interfaces are exact: [operations.md](operations.md) names each operation; this file fixes its names, fields and shapes. Where the two differ, this file wins.

## Records (the same fields in both apps)

| Record | Fields |
|---|---|
| Cleaner | `id` (int), `name` (string) |
| Client | `id` (int), `name` (string), `address` (string or null) |
| TimeEntry | `cleanerId` (int), `arrivedAt` (string or null), `departedAt` (string or null), `secondsWorked` (int or null) |
| Job | `id`, `clientId`, `cleanersNeeded`, `lengthMinutes` (ints), `requestedDate`, `date` (`YYYY-MM-DD`), `startMinute`, `endMinute` (ints, minutes from midnight), `cleanerIds` (ints, ascending), `status` (`booked`, `in_progress`, `complete`, `cancelled`), `timeEntries` (one per assigned cleaner) |
| InvoiceLine | `cleanerId` (int), `cleanerName` (string), `secondsWorked` (int), `chargeCents` (int) |
| Invoice | `id`, `jobId` (ints), `clientName` (string), `lines`, `totalCents` (int), `settled` (bool) |
| Utilization | `cleanerId` (int), `date` (`YYYY-MM-DD`), `daySeconds`, `weekSeconds` (ints), `dayPercent`, `weekPercent` (numbers: seconds ÷ 28,800 × 100 and ÷ 144,000 × 100) |

Timestamps are local `YYYY-MM-DDTHH:MM:SS`. When several sets of cleaners are free for the earliest slot, the job gets the free cleaners with the lowest ids (research D4).

## Desktop (Python)

- Started with `python3 -m desktop.cleaning.server --data PATH --port N`, run from the repository root; it serves until stopped.
- Request and response bodies use the field names above. A single record is a JSON object; a list is a JSON array.
- Bodies: `POST /api/cleaners` and `PUT /api/cleaners/{id}` `{"name"}`; clients `{"name", "address"}`; `POST /api/jobs` and `PUT /api/jobs/{id}` `{"clientId", "cleanersNeeded", "lengthMinutes", "requestedDate"}` (on PUT, fields left out are unchanged); `/arrive` and `/depart` `{"cleanerId", "timestamp"}`; `/extend` `{"cleanerId", "minutes"}`; `/pay` `{"amountCents"}`.
- Field operations and payment return the updated job or invoice. `DELETE` returns 204, or 200 with a body. `GET /api/utilization?date=` returns one Utilization a cleaner.
- Error status: `invalid_input` 400, `not_found` 404, `unschedulable`, `invalid_state` and `payment_mismatch` 409.

## Mobile (Swift)

Package `mobile/`, library `CleaningCore`. The records above are public `Codable, Equatable` structs with those property names (optional where "or null"; `status` a `String`). Errors:

```swift
public struct CleaningError: Error, Equatable { public let code: String; public let message: String }
```

```swift
public final class CleaningService {
    public init(storeURL: URL) throws                      // missing file: empty data
    public func createCleaner(name: String) throws -> Cleaner
    public func updateCleaner(id: Int, name: String) throws -> Cleaner
    public func deleteCleaner(id: Int) throws
    public func getCleaner(id: Int) throws -> Cleaner
    public func listCleaners() -> [Cleaner]
    public func createClient(name: String, address: String?) throws -> Client
    public func updateClient(id: Int, name: String, address: String?) throws -> Client
    public func deleteClient(id: Int) throws
    public func getClient(id: Int) throws -> Client
    public func listClients() -> [Client]
    public func bookJob(clientId: Int, cleanersNeeded: Int, lengthMinutes: Int, requestedDate: String) throws -> Job
    public func updateJob(id: Int, clientId: Int?, cleanersNeeded: Int?, lengthMinutes: Int?, requestedDate: String?) throws -> Job
    public func deleteJob(id: Int) throws
    public func getJob(id: Int) throws -> Job
    public func listJobs() -> [Job]
    public func cleanerDay(cleanerId: Int, date: String) throws -> [Job]
    public func arrive(jobId: Int, cleanerId: Int, timestamp: String) throws -> Job
    public func depart(jobId: Int, cleanerId: Int, timestamp: String) throws -> Job
    public func requestExtension(jobId: Int, cleanerId: Int, minutes: Int) throws -> Job
    public func listInvoices(settled: Bool?) -> [Invoice]
    public func getInvoice(id: Int) throws -> Invoice
    public func payInvoice(id: Int, amountCents: Int) throws -> Invoice
    public func utilization(cleanerId: Int, date: String) throws -> Utilization
}
```

Every successful change is saved to `storeURL` before the method returns; a new `CleaningService` on the same file sees it.
