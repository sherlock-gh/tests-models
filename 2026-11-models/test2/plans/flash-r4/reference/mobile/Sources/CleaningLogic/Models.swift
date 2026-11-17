import Foundation
import Darwin

public typealias Day = String
public enum ErrorKind: String, Codable, Sendable { case BadInput, NotFound, RuleViolation }
public struct AppError: Error {
    public let message: String
    public let kind: ErrorKind
    public init(kind: ErrorKind, message: String) { self.kind = kind; self.message = message }
}
public struct Cleaner: Codable { public var id: Int; public var name, phone, email: String; public var active: Bool }
public struct Client: Codable { public var id: Int; public var name, address, phone: String }
public struct Assignment: Codable { public var cleanerId: Int; public var arrive, depart: String?; public var extendedMinutes: Int }
public struct JobPart: Codable { public var partIndex: Int; public var day, start, end: String; public var assignments: [Assignment] }
public struct Job: Codable { public var id, clientId, cleanersNeeded: Int; public var expectedLengthHours: Double; public var requestedDay, status: String; public var parts: [JobPart]; public var invoiceId: Int? }
public struct InvoiceLine: Codable { public var cleanerId: Int; public var cleanerName: String; public var minutesWorked, amountCents: Int }
public struct Payment: Codable { public var amountCents: Int; public var paidAt: String }
public struct Invoice: Codable { public var id, jobId: Int; public var issuedAt: String; public var lines: [InvoiceLine]; public var totalCents: Int; public var settled: Bool; public var payment: Payment? }
public struct DayPart { public var jobId: Int; public var part: JobPart; public var client: Client?; public var coWorkers: [Int] }
public struct JobWithInvoice { public var job: Job; public var invoice: Invoice? }
public struct ExtensionResult { public var job: Job; public var rebookedJobIds: [Int] }
public struct RebookedJobs { public var rebookedJobIds: [Int] }
public struct CancelledJobs { public var cancelledJobIds: [Int] }
public struct UtilizationDay { public var cleanerId: Int; public var date: String; public var minutes, of: Int }
public struct UtilizationWeek { public var cleanerId: Int; public var weekStart: String; public var minutes, of: Int }
public struct Utilization { public var days: [UtilizationDay]; public var weeks: [UtilizationWeek] }

struct State: Codable {
    var cleaners: [Cleaner] = [], clients: [Client] = [], jobs: [Job] = [], invoices: [Invoice] = []
    var counters: [String: Int] = [:]
    mutating func issue(_ entity: String) -> Int { let id = (counters[entity] ?? 0) + 1; counters[entity] = id; return id }
}

public final class CleaningApp {
    let url: URL
    let zone: TimeZone
    let now: () -> Date
    let lock = NSRecursiveLock()
    var state: State
    var calendar: Calendar { var c = Calendar(identifier: .gregorian); c.timeZone = zone; return c }
    public init(dataFileURL: URL, timeZone: TimeZone = TimeZone(identifier: "America/Los_Angeles")!, now: @escaping () -> Date = Date.init) {
        url = dataFileURL; zone = timeZone; self.now = now
        let dec = JSONDecoder(); dec.keyDecodingStrategy = .convertFromSnakeCase
        state = (try? dec.decode(State.self, from: Data(contentsOf: url))) ?? State()
    }
    func change<T>(_ body: (inout State) throws -> T) throws -> T {
        lock.lock(); defer { lock.unlock() }
        var copy = state
        let result = try body(&copy)
        let enc = JSONEncoder(); enc.keyEncodingStrategy = .convertToSnakeCase; enc.outputFormatting = [.sortedKeys]
        let data = try enc.encode(copy)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let tmp = url.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
        do { try data.write(to: tmp); guard rename(tmp.path, url.path) == 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) } }
        catch { try? FileManager.default.removeItem(at: tmp); throw AppError(kind: .RuleViolation, message: "cannot save data: \(error)") }
        state = copy; return result
    }
    func bad(_ message: String) -> AppError { AppError(kind: .BadInput, message: message) }
    func missing(_ message: String) -> AppError { AppError(kind: .NotFound, message: message) }
    func conflict(_ message: String) -> AppError { AppError(kind: .RuleViolation, message: message) }
    func valid(_ values: String...) throws { if values.contains(where: { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) { throw bad("required field is empty") } }
    func format(_ date: Date) -> String { let f = DateFormatter(); f.timeZone = zone; f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd'T'HH:mm"; return f.string(from: date) }
    func parse(_ value: String) -> Date? { let f = DateFormatter(); f.timeZone = zone; f.locale = Locale(identifier: "en_US_POSIX"); f.isLenient = false; f.dateFormat = "yyyy-MM-dd'T'HH:mm"; return f.date(from: value) }
    func dayDate(_ value: Day) -> Date? { parse(value + "T08:00").flatMap { format($0).hasPrefix(value + "T") ? $0 : nil } }
    func addDays(_ value: Day, _ count: Int) -> Day { String(format(calendar.date(byAdding: .day, value: count, to: dayDate(value)!)!).prefix(10)) }
    func minute(_ value: Date) -> String { format(value) }
    func future(_ j: Job) -> Bool { j.parts.allSatisfy { $0.assignments.allSatisfy { $0.arrive == nil } } }
}
