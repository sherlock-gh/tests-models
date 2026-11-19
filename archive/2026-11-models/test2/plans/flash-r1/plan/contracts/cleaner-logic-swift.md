# Contract: Cleaner Logic Swift Package (CleanerApp)

**Form**: Swift package `CleaningLogic`, Swift 5.9+, Foundation only, **no UI** (problem statement known limit). Public API is the contract; data persists to the package app's own local JSON file. Same rule set as `shared/rule-spec.md` — parity asserted by mirrored scenario tests.

```swift
public struct Store {
    public init(fileURL: URL)                         // own local file, loads on init
    public func save() throws                          // atomic write

    // Records (FR-001) — all mutating ops are all-or-nothing (FR-016)
    public func addCleaner(name: String) throws -> Cleaner
    public func updateCleaner(_ c: Cleaner) throws
    public func deleteCleaner(id: Int) throws          // rebooks future jobs or throws .notEnoughCleaners (nothing changes)
    public func addClient(name: String) throws -> Client
    public func updateClient(_ c: Client) throws
    public func deleteClient(id: Int) throws           // cancels future jobs; invoices untouched

    // Booking (FR-002..FR-005)
    public func bookJob(clientID: Int, cleanersRequired: Int,
                        expectedLength: TimeInterval,  // hours; > 9h -> throws .jobTooLong
                        requestedDay: Date) throws -> Job

    // Field (FR-006..FR-009)
    public func jobs(forCleaner id: Int, on day: Date) -> [Job]
    public func arrive(cleanerID: Int, jobID: Int, at t: Date) throws
    public func depart(cleanerID: Int, jobID: Int, at t: Date) throws // last depart issues invoice atomically
    public func extend(cleanerID: Int, jobID: Int) throws             // +20 min + cascade (FR-009)

    // Billing (FR-012..FR-015)
    public func invoice(forJob id: Int) -> Invoice?
    public func recordPayment(invoiceID: Int, amount: Decimal, at t: Date) throws // full-equal only
    public func utilizationReports(day: Date) -> [UtilizationReport]
}

public enum CleaningError: Error, Equatable {
    case notFound(String)                 // missing cleaner/client/job/invoice
    case invalidInput(String)             // empty name, bad headcount, non-positive length
    case jobTooLong                       // > 9 h at booking (FR-002)
    case noFeasibleSlot                   // no slot / not enough cleaners (FR-003, edge cases)
    case tapOutOfOrder(String)            // arrive/depart misuse (US2-AC3)
    case wrongCleaner                     // tap on job not assigned to cleaner
    case paymentAmountMismatch            // partial/other amount (FR-013)
    case alreadySettled
    case notEnoughCleaners                // delete/rebook would strand a job (edge case)
}
```

Entities (`Cleaner`, `Client`, `Job`, `JobAssignment`, `Invoice`, `InvoiceLine`, `UtilizationReport`) mirror [../data-model.md](../data-model.md) field-for-field; money is ` Decimal`, times `Date` at minute granularity.

**Parity gate**: `Tests/CleaningLogicTests/` replays the same scenario table as `tests/` on the Python side (US1–US5 acceptance scenarios + all Edge Cases). Both sides must produce identical bookings, worked times, line amounts, totals, settlement states, and error cases for the same inputs.
