// Flash-Next's plan, the cleaner package's records (contracts/cleaner-logic-swift.md, exact-interfaces.md)
import Foundation

public struct Cleaner: Codable, Equatable { public let id: Int; public var name: String }
public struct Client: Codable, Equatable { public let id: Int; public var name: String }

public struct JobAssignment: Codable, Equatable {
    public var cleanerID: Int
    public var arrival: Date?
    public var departure: Date?
    public var workedMinutes: Int?
}

public struct Job: Codable, Equatable {
    public let id: Int
    public var clientID: Int
    public var requestedDay: Date
    public var expectedLengthMinutes: Int
    public var cleanersRequired: Int
    public var bookedStart: Date
    public var bookedEnd: Date
    public var state: String
    public var assignments: [JobAssignment]
    public var invoiceID: Int?
}

public struct InvoiceLine: Codable, Equatable { public var cleanerID: Int; public var workedMinutes: Int; public var amount: Decimal }

public struct Invoice: Codable, Equatable {
    public let id: Int
    public var jobID: Int
    public var issuedAt: Date
    public var lines: [InvoiceLine]
    public var total: Decimal
    public var settled: Bool
    public var paymentAmount: Decimal?
    public var paymentDate: Date?
}

public struct UtilizationReport: Codable, Equatable { public var cleanerID: Int; public var dayWorkedMinutes: Int; public var weekWorkedMinutes: Int }

public enum CleaningError: Error, Equatable {
    case notFound(String)
    case invalidInput(String)
    case jobTooLong
    case noFeasibleSlot
    case tapOutOfOrder(String)
    case wrongCleaner
    case paymentAmountMismatch
    case alreadySettled
    case notEnoughCleaners
}
