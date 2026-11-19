// The rules (contracts/rules-core.md), as the Python reference: each operation works on a copy of
// the state and keeps and writes it only if it succeeds. Times are in the injected time zone.
import Foundation

let dayStart = 480, dayEnd = 1020, partLength = 480, searchDays = 90, rate = 4500
let gap = 60
let noSlot = "No slot for this job within 90 days of the requested day."

public final class CleaningStore {
    let url: URL
    let cal: Calendar
    var s: State

    public init(fileURL: URL, timeZone: TimeZone) throws {
        url = fileURL
        var c = Calendar(identifier: .gregorian); c.timeZone = timeZone; cal = c
        if FileManager.default.fileExists(atPath: fileURL.path) {
            guard let d = try? Data(contentsOf: fileURL), let st = try? CleaningStore.decoder.decode(State.self, from: d) else {
                throw CleaningError(message: "the data file \(fileURL.path) can't be read")
            }
            s = st
        } else { s = State() }
    }

    static let decoder = JSONDecoder(), encoder = JSONEncoder()

    func run<T>(_ f: (inout State) throws -> T) throws -> T {
        var copy = s
        let out = try f(&copy)
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try CleaningStore.encoder.encode(copy).write(to: url, options: .atomic)
        } catch { throw CleaningError(message: "could not write the data file: \(error)") }
        s = copy
        return out
    }

    // ---- time
    func day(_ c: DateComponents) throws -> Date {
        guard let y = c.year, let m = c.month, let d = c.day,
              let date = cal.date(from: DateComponents(year: y, month: m, day: d)),
              cal.component(.day, from: date) == d, cal.component(.month, from: date) == m else {
            throw CleaningError(message: "not a day: \(c)")
        }
        return date
    }
    func at(_ day: Date, _ minute: Int) -> Date { cal.date(byAdding: .minute, value: minute, to: day)! }
    func addDays(_ day: Date, _ n: Int) -> Date { cal.date(byAdding: .day, value: n, to: day)! }
    func isWeekday(_ d: Date) -> Bool { let w = cal.component(.weekday, from: d); return w != 1 && w != 7 }
    func clashes(_ a: JobPart, _ b: JobPart) -> Bool {
        let g = TimeInterval(gap * 60)
        return a.start < b.end.addingTimeInterval(g) && b.start < a.end.addingTimeInterval(g)
    }
    func minutes(_ a: Date, _ b: Date) -> Int { Int(b.timeIntervalSince(a) / 60) }

    // ---- records
    static func name(_ n: String) throws -> String {
        let t = n.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { throw CleaningError(message: "a name is required") }
        return t
    }

    public func createCleaner(name: String) throws -> Cleaner {
        try run { s in let c = Cleaner(id: s.next("cleaners"), name: try CleaningStore.name(name)); s.cleaners.append(c); return c }
    }
    public func cleaners() -> [Cleaner] { s.cleaners }
    public func updateCleaner(id: Int, name: String) throws -> Cleaner {
        try run { s in
            guard let i = s.cleaners.firstIndex(where: { $0.id == id }) else { throw CleaningError(message: "no cleaner \(id)") }
            s.cleaners[i].name = try CleaningStore.name(name); return s.cleaners[i]
        }
    }
    public func deleteCleaner(id: Int) throws {
        try run { s in
            guard s.cleaners.contains(where: { $0.id == id }) else { throw CleaningError(message: "no cleaner \(id)") }
            s.cleaners.removeAll { $0.id == id }
            for i in s.jobs.indices where s.jobs[i].cleanerIds.contains(id) {
                switch s.jobs[i].status {
                case .booked: try place(&s, i, floor: nil, crew: nil)
                case .inProgress:
                    s.jobs[i].cleanerIds.removeAll { $0 == id }
                    s.jobs[i].taps.removeAll { $0.cleanerId == id }
                    _ = maybeComplete(&s, i, at: nil)
                default: break
                }
            }
        }
    }
    public func createClient(name: String) throws -> Client {
        try run { s in let c = Client(id: s.next("clients"), name: try CleaningStore.name(name)); s.clients.append(c); return c }
    }
    public func clients() -> [Client] { s.clients }
    public func updateClient(id: Int, name: String) throws -> Client {
        try run { s in
            guard let i = s.clients.firstIndex(where: { $0.id == id }) else { throw CleaningError(message: "no client \(id)") }
            s.clients[i].name = try CleaningStore.name(name); return s.clients[i]
        }
    }
    public func deleteClient(id: Int) throws {
        try run { s in
            guard s.clients.contains(where: { $0.id == id }) else { throw CleaningError(message: "no client \(id)") }
            s.clients.removeAll { $0.id == id }
            for i in s.jobs.indices where s.jobs[i].clientId == id && s.jobs[i].status == .booked { s.jobs[i].status = .cancelled }
        }
    }

    // ---- booking
    func lengths(_ total: Int) -> [Int] {
        if total <= partLength { return [total] }
        return Array(repeating: partLength, count: total / partLength) + (total % partLength > 0 ? [total % partLength] : [])
    }

    func candidates(_ first: Date, _ total: Int, _ floor: Date?) -> [[JobPart]] {
        guard isWeekday(first) else { return [] }
        let ls = lengths(total)
        if ls.count == 1 {
            var out = [[JobPart]]()
            for m in stride(from: dayStart, through: dayEnd - ls[0], by: 15) {
                let p = JobPart(start: at(first, m), end: at(first, m + ls[0]))
                if let f = floor, p.start < f { continue }
                out.append([p])
            }
            return out
        }
        var days = [Date](), d = first
        while days.count < ls.count { if isWeekday(d) { days.append(d) }; d = addDays(d, 1) }
        let parts = zip(days, ls).map { JobPart(start: at($0, dayStart), end: at($0, dayStart + $1)) }
        if let f = floor, parts[0].start < f { return [] }
        return [parts]
    }

    func busy(_ s: State, _ cleaner: Int, skip: Int) -> [JobPart] {
        s.jobs.filter { $0.status != .cancelled && $0.id != skip && $0.cleanerIds.contains(cleaner) }.flatMap(\.parts)
    }

    func place(_ s: inout State, _ i: Int, floor: Date?, crew: [Int]?) throws {
        let job = s.jobs[i]
        var start = try day(job.requestedDay)
        if let f = floor, cal.startOfDay(for: f) > start { start = cal.startOfDay(for: f) }
        let pool = crew ?? s.cleaners.map(\.id).sorted()
        let books = Dictionary(uniqueKeysWithValues: pool.map { ($0, busy(s, $0, skip: job.id)) })
        for k in 0...searchDays {
            for parts in candidates(addDays(start, k), job.expectedLengthMinutes, floor) {
                let free = pool.filter { c in !parts.contains { p in books[c]!.contains { clashes(p, $0) } } }
                if free.count >= job.cleanersNeeded {
                    s.jobs[i].parts = parts; s.jobs[i].cleanerIds = Array(free.prefix(job.cleanersNeeded)); return
                }
            }
        }
        throw CleaningError(message: noSlot)
    }

    func checkFields(_ n: Int, _ length: Int, _ day: DateComponents) throws {
        if !(1...3).contains(n) { throw CleaningError(message: "cleanersNeeded must be 1, 2 or 3") }
        if length <= 0 { throw CleaningError(message: "the expected length must be above 0 minutes") }
        _ = try self.day(day)
    }

    public func bookJob(_ req: BookingRequest) throws -> Job {
        try checkFields(req.cleanersNeeded, req.expectedLengthMinutes, req.requestedDay)
        return try run { s in
            guard s.clients.contains(where: { $0.id == req.clientId }) else { throw CleaningError(message: "no client \(req.clientId)") }
            let rd = DateComponents(year: req.requestedDay.year, month: req.requestedDay.month, day: req.requestedDay.day)
            s.jobs.append(Job(id: -1, clientId: req.clientId, cleanersNeeded: req.cleanersNeeded, expectedLengthMinutes: req.expectedLengthMinutes,
                              requestedDay: rd, cleanerIds: [], status: .booked, parts: [], invoiceId: nil, invoice: nil, taps: []))
            try place(&s, s.jobs.count - 1, floor: nil, crew: nil)
            s.jobs[s.jobs.count - 1].id = s.next("jobs")
            return s.jobs[s.jobs.count - 1]
        }
    }

    func index(_ s: State, job id: Int) throws -> Int {
        guard let i = s.jobs.firstIndex(where: { $0.id == id }) else { throw CleaningError(message: "no job \(id)") }
        return i
    }

    public func job(id: Int) throws -> Job { let i = try index(s, job: id); return s.jobs[i] }

    public func deleteJob(id: Int) throws {
        try run { s in
            let i = try index(s, job: id)
            if s.jobs[i].invoiceId != nil { throw CleaningError(message: "invoice has been issued") }
            s.jobs.remove(at: i)
        }
    }

    // ---- the field
    public func jobsForToday(cleanerId: Int, on day: DateComponents) throws -> [Job] {
        guard s.cleaners.contains(where: { $0.id == cleanerId }) else { throw CleaningError(message: "no cleaner \(cleanerId)") }
        let d = try self.day(day)
        return s.jobs.compactMap { j -> (Date, Job)? in
            guard j.status != .cancelled, j.cleanerIds.contains(cleanerId),
                  let p = j.parts.first(where: { cal.isDate($0.start, inSameDayAs: d) }) else { return nil }
            return (p.start, j)
        }.sorted { $0.0 < $1.0 }.map(\.1)
    }

    func tapTarget(_ s: State, _ jobId: Int, _ cleanerId: Int) throws -> Int {
        let i = try index(s, job: jobId)
        if !s.jobs[i].cleanerIds.contains(cleanerId) { throw CleaningError(message: "cleaner \(cleanerId) is not on job \(jobId)") }
        if s.jobs[i].status != .booked && s.jobs[i].status != .inProgress { throw CleaningError(message: "job \(jobId) is \(s.jobs[i].status.rawValue)") }
        return i
    }

    func toMinute(_ d: Date) -> Date { cal.dateInterval(of: .minute, for: d)!.start }

    public func arrive(jobId: Int, cleanerId: Int, atInstant date: Date) throws -> Job {
        try run { s in
            let i = try tapTarget(s, jobId, cleanerId)
            let mine = s.jobs[i].taps.filter { $0.cleanerId == cleanerId }
            if mine.last?.kind == .arrive { throw CleaningError(message: "already arrived: tap Depart first") }
            if mine.filter({ $0.kind == .depart }).count >= s.jobs[i].parts.count { throw CleaningError(message: "this cleaner has finished the job") }
            s.jobs[i].taps.append(Tap(cleanerId: cleanerId, kind: .arrive, instant: toMinute(date)))
            s.jobs[i].status = .inProgress
            return s.jobs[i]
        }
    }

    public func depart(jobId: Int, cleanerId: Int, atInstant date: Date) throws -> Job {
        try run { s in
            let i = try tapTarget(s, jobId, cleanerId)
            let mine = s.jobs[i].taps.filter { $0.cleanerId == cleanerId }
            guard let last = mine.last, last.kind == .arrive else { throw CleaningError(message: "no Arrive to depart from") }
            let when = toMinute(date)
            if when < last.instant { throw CleaningError(message: "Depart is before the Arrive") }
            s.jobs[i].taps.append(Tap(cleanerId: cleanerId, kind: .depart, instant: when))
            var out = s.jobs[i]
            out.invoice = maybeComplete(&s, i, at: when)
            out.status = s.jobs[i].status; out.invoiceId = s.jobs[i].invoiceId
            return out
        }
    }

    func worked(_ j: Job, _ c: Int, from lo: Date? = nil, to hi: Date? = nil) -> Int {
        let mine = j.taps.filter { $0.cleanerId == c }
        var total = 0, k = 0
        while k + 1 < mine.count {
            var a = mine[k].instant, d = mine[k + 1].instant
            if let lo = lo, a < lo { a = lo }
            if let hi = hi, d > hi { d = hi }
            if d > a { total += minutes(a, d) }
            k += 2
        }
        return total
    }

    func maybeComplete(_ s: inout State, _ i: Int, at when: Date?) -> Invoice? {
        let j = s.jobs[i]
        guard !j.cleanerIds.isEmpty else { return nil }
        for c in j.cleanerIds {
            let mine = j.taps.filter { $0.cleanerId == c }
            if mine.filter({ $0.kind == .depart }).count < j.parts.count || mine.last?.kind != .depart { return nil }
        }
        let lines = j.cleanerIds.map { c -> InvoiceLine in
            let m = worked(j, c); return InvoiceLine(cleanerId: c, minutesWorked: m, cents: (m * rate + 30) / 60)
        }
        let inv = Invoice(id: s.next("invoices"), jobId: j.id, issuedAt: when ?? j.taps.map(\.instant).max()!, lines: lines,
                          totalCents: lines.map(\.cents).reduce(0, +), settled: false)
        s.invoices.append(inv)
        s.jobs[i].status = .complete; s.jobs[i].invoiceId = inv.id
        return inv
    }

    public func requestMoreTime(jobId: Int, cleanerId: Int) throws -> MoreTimeOutcome {
        try run { s in
            let i = try index(s, job: jobId)
            let mine = s.jobs[i].taps.filter { $0.cleanerId == cleanerId }
            guard s.jobs[i].cleanerIds.contains(cleanerId), s.jobs[i].status == .inProgress, mine.last?.kind == .arrive else {
                throw CleaningError(message: "more time is for a cleaner who has arrived and not departed")
            }
            let k = min(mine.filter { $0.kind == .depart }.count, s.jobs[i].parts.count - 1)
            s.jobs[i].parts[k].end = at(s.jobs[i].parts[k].end, 20)
            let floor = s.jobs[i].parts[k].end.addingTimeInterval(TimeInterval(gap * 60))
            var moved = [Int]()
            while true {
                let job = s.jobs[i], crew = Set(job.cleanerIds)
                let hit = s.jobs.indices.filter { h in
                    let o = s.jobs[h]
                    return o.id != job.id && o.status == .booked && !crew.isDisjoint(with: o.cleanerIds)
                        && job.parts.contains { p in o.parts.contains { clashes(p, $0) } }
                }.min { s.jobs[$0].parts[0].start < s.jobs[$1].parts[0].start }
                guard let h = hit else { break }
                try place(&s, h, floor: floor, crew: s.jobs[h].cleanerIds)
                moved.append(s.jobs[h].id)
            }
            var rebooked = [RebookedJob]()
            for m in moved { let h = try index(s, job: m); rebooked.append(RebookedJob(jobId: m, parts: s.jobs[h].parts)) }
            return MoreTimeOutcome(job: s.jobs[i], rebooked: rebooked)
        }
    }

    // ---- invoices
    public func invoices() -> [Invoice] { s.invoices }
    public func invoice(id: Int) throws -> Invoice {
        guard let v = s.invoices.first(where: { $0.id == id }) else { throw CleaningError(message: "no invoice \(id)") }
        return v
    }
    public func pay(invoiceId: Int, amountCents: Int) throws -> Invoice {
        try run { s in
            guard let i = s.invoices.firstIndex(where: { $0.id == invoiceId }) else { throw CleaningError(message: "no invoice \(invoiceId)") }
            if s.invoices[i].settled { throw CleaningError(message: "this invoice is already settled") }
            if amountCents != s.invoices[i].totalCents { throw CleaningError(message: "an invoice is paid in full in one payment: \(s.invoices[i].totalCents) cents") }
            s.payments.append(Payment(id: s.next("payments"), invoiceId: invoiceId, amountCents: amountCents, paidAt: Date()))
            s.invoices[i].settled = true
            return s.invoices[i]
        }
    }
    public func updateInvoice(id: Int, totalCents: Int) throws -> Invoice { throw CleaningError(message: "issued invoices never change") }
    public func deleteInvoice(id: Int) throws { throw CleaningError(message: "issued invoices are never deleted") }

    // ---- utilization
    func report(_ days: [Date], _ of: Int) -> [UtilizationEntry] {
        s.cleaners.sorted { $0.id < $1.id }.map { c in
            let m = days.reduce(0) { acc, d in acc + s.jobs.reduce(0) { $0 + worked($1, c.id, from: d, to: addDays(d, 1)) } }
            return UtilizationEntry(cleanerId: c.id, name: c.name, hoursWorked: Double(m) / 60, hoursOf: of)
        }
    }
    public func dailyUtilization(date: DateComponents) -> [UtilizationEntry] {
        guard let d = try? day(date) else { return [] }
        return report([d], 8)
    }
    public func weeklyUtilization(weekOf monday: DateComponents) -> [UtilizationEntry] {
        guard let d = try? day(monday) else { return [] }
        return report((0..<7).map { addDays(d, $0) }, 40)
    }
}
