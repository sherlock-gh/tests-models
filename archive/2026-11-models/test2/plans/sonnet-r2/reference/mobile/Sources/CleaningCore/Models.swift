import Foundation

public struct CleaningError: Error, Equatable {
    public let code: String
    public let message: String
    public init(code: String, message: String) { self.code = code; self.message = message }
}

public struct Cleaner: Codable, Equatable { public let id: Int; public var name: String }

public struct Client: Codable, Equatable { public let id: Int; public var name: String; public var address: String? }

public struct TimeEntry: Codable, Equatable {
    public let cleanerId: Int
    public var arrivedAt: String?
    public var departedAt: String?
    public var secondsWorked: Int?
}

public struct Job: Codable, Equatable {
    public let id: Int
    public var clientId: Int
    public var cleanersNeeded: Int
    public var lengthMinutes: Int
    public var requestedDate: String
    public var date: String
    public var startMinute: Int
    public var endMinute: Int
    public var cleanerIds: [Int]
    public var status: String
    public var timeEntries: [TimeEntry]
}

public struct InvoiceLine: Codable, Equatable {
    public let cleanerId: Int
    public let cleanerName: String
    public let secondsWorked: Int
    public let chargeCents: Int
}

public struct Invoice: Codable, Equatable {
    public let id: Int
    public let jobId: Int
    public let clientName: String
    public let lines: [InvoiceLine]
    public let totalCents: Int
    public var settled: Bool
}

public struct Utilization: Codable, Equatable {
    public let cleanerId: Int
    public let date: String
    public let daySeconds: Int
    public let weekSeconds: Int
    public let dayPercent: Double
    public let weekPercent: Double
}

struct Payment: Codable, Equatable { let invoiceId: Int; let amountCents: Int }

struct State: Codable, Equatable {
    var next = [String: Int]()
    var cleaners = [Cleaner]()
    var clients = [Client]()
    var jobs = [Job]()
    var invoices = [Invoice]()
    var payments = [Payment]()

    mutating func newId(_ kind: String) -> Int { next[kind, default: 0] += 1; return next[kind]! }
}

/// Dates as day numbers (days since 1970-01-01), timestamps as seconds: integer arithmetic only.
enum Calendar0 {
    static func days(_ s: String) -> Int? {
        let p = s.split(separator: "-", omittingEmptySubsequences: false)
        guard s.count == 10, p.count == 3, let y = Int(p[0]), let m = Int(p[1]), let d = Int(p[2]),
              (1...12).contains(m), d >= 1, d <= monthDays(y, m) else { return nil }
        let yy = m <= 2 ? y - 1 : y
        let era = (yy >= 0 ? yy : yy - 399) / 400
        let yoe = yy - era * 400
        let doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1
        let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy
        return era * 146097 + doe - 719468
    }

    static func string(_ z0: Int) -> String {
        let z = z0 + 719468
        let era = (z >= 0 ? z : z - 146096) / 146097
        let doe = z - era * 146097
        let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365
        let doy = doe - (365 * yoe + yoe / 4 - yoe / 100)
        let mp = (5 * doy + 2) / 153
        let d = doy - (153 * mp + 2) / 5 + 1
        let m = mp < 10 ? mp + 3 : mp - 9
        let y = yoe + era * 400 + (m <= 2 ? 1 : 0)
        return String(format: "%04d-%02d-%02d", y, m, d)
    }

    static func monthDays(_ y: Int, _ m: Int) -> Int {
        let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0
        return [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    }

    static func weekday(_ day: Int) -> Int { ((day % 7) + 7 + 3) % 7 }   // 0 = Monday

    static func seconds(_ ts: String) -> Int? {
        let parts = ts.split(separator: "T", omittingEmptySubsequences: false)
        guard ts.count == 19, parts.count == 2, let d = days(String(parts[0])) else { return nil }
        let t = parts[1].split(separator: ":", omittingEmptySubsequences: false)
        guard t.count == 3, let h = Int(t[0]), let mi = Int(t[1]), let s = Int(t[2]),
              (0...23).contains(h), (0...59).contains(mi), (0...59).contains(s) else { return nil }
        return d * 86400 + h * 3600 + mi * 60 + s
    }
}
