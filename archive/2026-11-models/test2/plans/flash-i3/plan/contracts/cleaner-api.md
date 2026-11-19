# Contract: Cleaner-Side Swift API (CleaningKit package)

**Date**: 2026-11-13 | **Plan**: [plan.md](plan.md)

`CleaningKit` is a SwiftPM library (no UI) holding the cleaner-side logic and the same rule
engine. All operations are methods on one class which owns the store file:

```swift
public final class CleaningStore {
    public init(fileURL: URL, timeZone: TimeZone) throws
    // throws CleaningError on an unreadable/corrupt data file (research R8); never crashes
}
```

Every throwing method raises `CleaningError(message: String)` — the field UI shows the
message, data on disk is unchanged, and the store stays usable (rules-core I10). Money is
`Int` cents, times are `Date`/`Calendar`-based in the injected `timeZone`.

## Records (back-office-shaped CRUD, mirrored so the app can seed its own file)

```swift
public func createCleaner(name: String) throws -> Cleaner          // .name empty -> throw
public func cleaners() -> [Cleaner]
public func updateCleaner(id: Int, name: String) throws -> Cleaner // unknown id -> throw
public func deleteCleaner(id: Int) throws                          // future jobs rebooked (I9)
public func createClient(name: String) throws -> Client
public func clients() -> [Client]
public func updateClient(id: Int, name: String) throws -> Client
public func deleteClient(id: Int) throws                           // future jobs cancelled
```

## Booking

```swift
public struct BookingRequest {
    public var clientId: Int
    public var cleanersNeeded: Int          // 1...3 else throw
    public var expectedLengthMinutes: Int   // > 0 else throw
    public var requestedDay: DateComponents // YYYY-MM-DD
}
public func bookJob(_ req: BookingRequest) throws -> Job
// earliest quarter-hour slot >= requested day where cleanersNeeded cleaners are free,
// 90-day search, >8 h split parts same crew; exhaustion throws
// "No slot for this job within 90 days of the requested day." with nothing written (I5)
public func job(id: Int) throws -> Job                              // unknown -> throw
public func deleteJob(id: Int) throws // issued-invoice job -> throw "invoice has been issued"
```

## Field operations (what the cleaner app calls)

```swift
public func jobsForToday(cleanerId: Int, on day: DateComponents) throws -> [Job]
// jobs assigned to cleaner starting that day: client, start time, expected length (US2 AC1)

public func arrive(jobId: Int, cleanerId: Int, atInstant date: Date) throws -> Job
// to-the-minute tap; second Arrive for same cleaner-job -> throw

public func depart(jobId: Int, cleanerId: Int, atInstant date: Date) throws -> Job
// Depart without prior Arrive -> throw. Last cleaner's Depart issues the invoice in the
// same write and the returned job carries `invoice` (I7).

public func requestMoreTime(jobId: Int, cleanerId: Int) throws -> MoreTimeOutcome
// 20-minute step; only a cleaner who arrived and not departed (else throw); no cap, past
// 17:00 allowed. Later < 1 h-shadow jobs rebooked by booking rule with floor at new end +
// 1 h, cascading; all-or-nothing (I1, G14).
public struct MoreTimeOutcome { public var job: Job; public var rebooked: [RebookedJob] }
```

## Invoices, settlement, utilization

```swift
public func invoices() -> [Invoice]                 // lines, totals, settled flag (I7/I8)
public func invoice(id: Int) throws -> Invoice      // unknown -> throw
public func pay(invoiceId: Int, amountCents: Int) throws -> Invoice
// exact full amount only; anything else throws; settled invoice -> throw (I8)
public func updateInvoice(id: Int, ...) / deleteInvoice(id:)  // always throw (I9)

public func dailyUtilization(date: DateComponents) -> [UtilizationEntry]
public func weeklyUtilization(weekOf monday: DateComponents) -> [UtilizationEntry]
public struct UtilizationEntry {
    public var cleanerId: Int, name: String
    public var hoursWorked: Double   // minutes/60; midnight-split attribution (G9)
    public var hoursOf: Int           // 8 daily, 40 weekly; hoursWorked may exceed (G10)
}
// cleaner with no taps -> hoursWorked 0.0, never an error (US6 AC4)
```

## Shared invariants

`CleaningKit` MUST satisfy rules-core I1–I10 and every golden pin G1–G20 in
[rules-core.md](rules-core.md) through these calls, with the same data-file-independent
behavior as the desktop app but **no sharing of data with it**.
