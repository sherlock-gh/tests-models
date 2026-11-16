// The package's public records (contracts/cleaner-api.md, exact-interfaces.md).
import Foundation

public struct CleaningError: Error, CustomStringConvertible {
    public let message: String
    public init(message: String) { self.message = message }
    public var description: String { message }
}

public struct Cleaner: Codable, Equatable { public var id: Int; public var name: String }
public struct Client: Codable, Equatable { public var id: Int; public var name: String }

public enum JobStatus: String, Codable { case booked, inProgress = "in_progress", complete, cancelled }
public enum TapKind: String, Codable { case arrive, depart }

public struct JobPart: Codable, Equatable {
    public var start: Date
    public var end: Date
    public var durationMinutes: Int { Int(end.timeIntervalSince(start) / 60) }
}

public struct Tap: Codable, Equatable { public var cleanerId: Int; public var kind: TapKind; public var instant: Date }

public struct InvoiceLine: Codable, Equatable { public var cleanerId: Int; public var minutesWorked: Int; public var cents: Int }

public struct Invoice: Codable, Equatable {
    public var id: Int
    public var jobId: Int
    public var issuedAt: Date
    public var lines: [InvoiceLine]
    public var totalCents: Int
    public var settled: Bool
}

public struct Job: Codable, Equatable {
    public var id: Int
    public var clientId: Int
    public var cleanersNeeded: Int
    public var expectedLengthMinutes: Int
    public var requestedDay: DateComponents
    public var cleanerIds: [Int]
    public var status: JobStatus
    public var parts: [JobPart]
    public var invoiceId: Int?
    public var invoice: Invoice?
    public var taps: [Tap]
}

public struct BookingRequest {
    public var clientId: Int
    public var cleanersNeeded: Int
    public var expectedLengthMinutes: Int
    public var requestedDay: DateComponents
    public init(clientId: Int, cleanersNeeded: Int, expectedLengthMinutes: Int, requestedDay: DateComponents) {
        self.clientId = clientId; self.cleanersNeeded = cleanersNeeded
        self.expectedLengthMinutes = expectedLengthMinutes; self.requestedDay = requestedDay
    }
}

public struct RebookedJob: Equatable { public var jobId: Int; public var parts: [JobPart] }
public struct MoreTimeOutcome { public var job: Job; public var rebooked: [RebookedJob] }

public struct UtilizationEntry: Equatable {
    public var cleanerId: Int
    public var name: String
    public var hoursWorked: Double
    public var hoursOf: Int
}

struct Payment: Codable { var id: Int; var invoiceId: Int; var amountCents: Int; var paidAt: Date }

struct State: Codable {
    var seq = [String: Int]()
    var cleaners = [Cleaner](), clients = [Client](), jobs = [Job](), invoices = [Invoice](), payments = [Payment]()
    mutating func next(_ kind: String) -> Int { let n = (seq[kind] ?? 0) + 1; seq[kind] = n; return n }
}
