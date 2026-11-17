# Contract: Mobile Logic Package Public API (Swift)

SwiftPM package at `mobile/`, library target `CleaningLogic` (Foundation only, **no UI**,
FR-018). The cleaner's identity is supplied by whoever runs the package (Q6 — no
accounts). All failable operations `throw AppError` (struct with a `message` and a
`kind: BadInput | NotFound | RuleViolation`); callers display `message`, nothing changes
on throw (FR-019). Entities and JSON shapes are identical to
contracts/desktop-api.md / data-model.md — the two apps run the same rules on their own
file, never each other.

## Construction / persistence (research R8)

```swift
CleaningApp(dataFileURL: URL,
            timeZone: TimeZone = TimeZone(identifier: "America/Los_Angeles")!,
            now: () -> Date = Date.init)   // injectable clock for tests
```

Loads `dataFileURL` if it exists (persists across restarts, FR-018); every mutation
writes atomically (temp file + replace) under a lock.

## Back-office-grade CRUD (same rules as desktop — both apps enforce everything)

```swift
createCleaner(name: String, phone: String, email: String) throws -> Cleaner
readCleaner(id: Int) throws -> Cleaner            // throws NotFound
listCleaners() -> [Cleaner]
updateCleaner(id: Int, name: String, phone: String, email: String) throws -> Cleaner
deleteCleaner(id: Int) throws -> RebookedJobs     // future jobs re-booked, any free cleaners (FR-012)

createClient(name: String, address: String, phone: String) throws -> Client
readClient / listClients / updateClient            // mirror cleaner forms
deleteClient(id: Int) throws -> CancelledJobs      // future jobs cancelled (FR-012)

bookJob(clientId: Int, cleanersNeeded: Int /*1...3*/,
        expectedLengthHours: Double /*>0*/,
        requestedDay: Day /*YYYY-MM-DD*/) throws -> Job
    // booking rule: earliest quarter-hour slot >= requestedDay, weekdays 8:00–17:00,
    // strict >=1h spacing (12:00->13:00 ok, 12:45 no; 12:10->13:15), >8h split 8+8+rest
    // each part independently booked on a later workday; prefer first-part cleaners
    // if free, else use other free cleaners; 90-day horizon;
    // throws RuleViolation("no slot ...") with zero writes (FR-003..FR-006)
readJob / listJobs(from:to:clientId:)
updateJob(...) throws -> Job      // Q2: refused RuleViolation if overlap result, else stands
deleteJob(id: Int) throws         // RuleViolation if invoice issued (FR-013)
```

## Cleaner-facing field operations (FR-008–FR-011)

```swift
daySchedule(cleanerId: Int, on day: Day) -> [DayPart]
    // jobs with times, client, co-workers (US2-AC1)
arrive(jobId: Int, cleanerId: Int, at: Date) throws -> Job
    // to the minute; second arrive -> RuleViolation (Q5)
depart(jobId: Int, cleanerId: Int, at: Date) throws -> JobWithInvoice?
    // needs prior arrive, depart >= arrive (Q5); when the LAST assigned cleaner
    // departs, returns the freshly issued invoice (FR-014, FR-015)
extend(jobId: Int, cleanerId: Int, minutes: Int = 20, at: Date) throws -> ExtensionResult
    // 20-min steps, only arrived-and-not-departed, unlimited, may pass 17:00;
    // cascades re-booking of later jobs of every assigned cleaner (Q1: job moves as a
    // unit) floor newEnd+1h, repeat until clean; throws RuleViolation restoring all
    // schedules if a bumped job is unplaceable in horizon (Q9); result reports
    // rebookedJobIds
```

## Invoices, payments, utilization (FR-013–FR-017)

```swift
listInvoices(settled: Bool? = nil) -> [Invoice]
readInvoice(id: Int) throws -> Invoice        // no update/delete surface exists (FR-013)
recordPayment(invoiceId: Int, amountCents: Int) throws -> Invoice
    // == totalCents exactly -> settled; any other amount throws RuleViolation (FR-016)
utilization(cleanerId: Int, from: Day, to: Day) -> Utilization
    // per local calendar day x/480min and Mon–Sun week x/2400min, uncapped;
    // 22:00-02:00 -> 120/120 (FR-017, SC-007)
```

## Golden vectors (runnable in both test suites — parity anchor, research R5)

- 3 h 30 min tap pair → line 15750¢ ($157.50); 4 h → 18000¢; total 33750¢.
- End 12:00 → next allowed 13:00 (12:45 rejected by the free-check); end 12:10 → 13:15.
- Saturday-requested job books Monday 8:00.
- 10 h job = 8 h + 2 h on later workdays, each independently booked; prefer first-part cleaners if free, else use other free cleaners; 8 h fits 8:00–16:00.
- Three 20-min steps from a 12:00 end (new end 13:00) re-book the 13:15 later job to
  ≥ 14:00 by the booking rule (US4-AC1).
- Payment $337.00 on a 33750¢ invoice → throw, unsettled; 33750 → settled.
- Utilization: 9 h Monday → 540/480.
