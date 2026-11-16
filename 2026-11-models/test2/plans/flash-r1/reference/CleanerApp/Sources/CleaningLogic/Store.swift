// Flash-Next's plan, the rules (research D-3..D-9), as the Python reference: each operation works on a
// copy and keeps it only if it succeeds. Times are local (Calendar.current), to the minute.
import Foundation

struct State: Codable {
    var next = [String: Int]()
    var cleaners = [Cleaner](), clients = [Client](), jobs = [Job](), invoices = [Invoice]()
    mutating func newID(_ kind: String) -> Int { let n = (next[kind] ?? 0) + 1; next[kind] = n; return n }
}

final class Box { var s: State; init(_ s: State) { self.s = s } }

let dayStart = 480, dayEnd = 1020, maxLength = 540, horizon = 52
let gap = 60
var cal: Calendar { Calendar.current }
func startOfDay(_ d: Date) -> Date { cal.startOfDay(for: d) }
func minute(_ d: Date) -> Int { let c = cal.dateComponents([.hour, .minute], from: d); return c.hour! * 60 + c.minute! }
func at(_ day: Date, _ m: Int) -> Date { cal.date(byAdding: .minute, value: m, to: day)! }
func addDays(_ day: Date, _ n: Int) -> Date { cal.date(byAdding: .day, value: n, to: day)! }
func isWeekday(_ d: Date) -> Bool { let w = cal.component(.weekday, from: d); return w != 1 && w != 7 }
func cents(_ d: Decimal) -> Decimal { var x = d, r = Decimal(); NSDecimalRound(&r, &x, 2, .plain); return r }

public struct Store {
    let url: URL
    let box: Box

    public init(fileURL: URL) {
        url = fileURL
        let s = (try? Data(contentsOf: fileURL)).flatMap { try? JSONDecoder().decode(State.self, from: $0) }
        box = Box(s ?? State())
    }

    public func save() throws { try JSONEncoder().encode(box.s).write(to: url, options: .atomic) }

    func run<T>(_ f: (inout State) throws -> T) rethrows -> T {
        var s = box.s
        let out = try f(&s)
        box.s = s
        return out
    }

    // ---- records
    static func name(_ n: String) throws -> String {
        let t = n.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { throw CleaningError.invalidInput("a name is required") }
        return t
    }

    public func addCleaner(name: String) throws -> Cleaner {
        try run { s in let c = Cleaner(id: s.newID("cleaners"), name: try Store.name(name)); s.cleaners.append(c); return c }
    }
    public func updateCleaner(_ c: Cleaner) throws {
        try run { s in
            guard let i = s.cleaners.firstIndex(where: { $0.id == c.id }) else { throw CleaningError.notFound("cleaner \(c.id)") }
            s.cleaners[i].name = try Store.name(c.name)
        }
    }
    public func addClient(name: String) throws -> Client {
        try run { s in let c = Client(id: s.newID("clients"), name: try Store.name(name)); s.clients.append(c); return c }
    }
    public func updateClient(_ c: Client) throws {
        try run { s in
            guard let i = s.clients.firstIndex(where: { $0.id == c.id }) else { throw CleaningError.notFound("client \(c.id)") }
            s.clients[i].name = try Store.name(c.name)
        }
    }

    public func deleteCleaner(id: Int) throws {
        try run { s in
            guard let i = s.cleaners.firstIndex(where: { $0.id == id }) else { throw CleaningError.notFound("cleaner \(id)") }
            s.cleaners.remove(at: i)
            let mine = s.jobs.indices.filter { s.jobs[$0].state == "scheduled" && s.jobs[$0].assignments.contains { $0.cleanerID == id } }
                .sorted { s.jobs[$0].bookedStart < s.jobs[$1].bookedStart }
            for k in mine {
                let d = startOfDay(s.jobs[k].bookedStart), m = minute(s.jobs[k].bookedStart)
                s.jobs[k].assignments = []
                do { try Store.place(&s, k, from: d, floor: (d, m)) } catch { throw CleaningError.notEnoughCleaners }
            }
        }
    }

    public func deleteClient(id: Int) throws {
        try run { s in
            guard let i = s.clients.firstIndex(where: { $0.id == id }) else { throw CleaningError.notFound("client \(id)") }
            s.clients.remove(at: i)
            for k in s.jobs.indices where s.jobs[k].clientID == id && s.jobs[k].state == "scheduled" { s.jobs[k].state = "cancelled" }
        }
    }

    // ---- booking (D-3)
    static func free(_ s: State, _ c: Int, _ day: Date, _ start: Int, _ end: Int, skip: Int) -> Bool {
        for j in s.jobs where j.id != skip && j.state == "scheduled" && j.assignments.contains(where: { $0.cleanerID == c }) {
            guard startOfDay(j.bookedStart) == day else { continue }
            let js = minute(j.bookedStart), je = js + Int(j.bookedEnd.timeIntervalSince(j.bookedStart) / 60)
            if start < je + gap && js < end + gap { return false }
        }
        return true
    }

    static func place(_ s: inout State, _ k: Int, from: Date, floor: (Date, Int)? = nil) throws {
        let ids = s.cleaners.map(\.id).sorted(), n = s.jobs[k].cleanersRequired, len = s.jobs[k].expectedLengthMinutes
        if n > ids.count { throw CleaningError.noFeasibleSlot }
        var d = startOfDay(from), seen = 0
        while seen < horizon {
            if isWeekday(d) {
                seen += 1
                let lo = floor.map { $0.0 == d ? max(dayStart, $0.1) : dayStart } ?? dayStart
                var start = lo
                while start + len <= dayEnd {
                    let ok = ids.filter { free(s, $0, d, start, start + len, skip: s.jobs[k].id) }
                    if ok.count >= n {
                        s.jobs[k].bookedStart = at(d, start); s.jobs[k].bookedEnd = at(d, start + len)
                        s.jobs[k].assignments = ok.prefix(n).map { JobAssignment(cleanerID: $0, arrival: nil, departure: nil, workedMinutes: nil) }
                        return
                    }
                    start += 1
                }
            }
            d = addDays(d, 1)
        }
        throw CleaningError.noFeasibleSlot
    }

    public func bookJob(clientID: Int, cleanersRequired: Int, expectedLength: TimeInterval, requestedDay: Date) throws -> Job {
        try run { s in
            guard s.clients.contains(where: { $0.id == clientID }) else { throw CleaningError.notFound("client \(clientID)") }
            guard (1...3).contains(cleanersRequired) else { throw CleaningError.invalidInput("cleaners required must be 1, 2 or 3") }
            let mins = Int((expectedLength * 60).rounded())   // the contract: hours
            if mins <= 0 { throw CleaningError.invalidInput("the length must be more than 0") }
            if mins > maxLength { throw CleaningError.jobTooLong }
            let day = startOfDay(requestedDay)
            s.jobs.append(Job(id: s.newID("jobs"), clientID: clientID, requestedDay: day, expectedLengthMinutes: mins,
                              cleanersRequired: cleanersRequired, bookedStart: day, bookedEnd: day, state: "scheduled", assignments: [], invoiceID: nil))
            try Store.place(&s, s.jobs.count - 1, from: day)
            return s.jobs[s.jobs.count - 1]
        }
    }

    public func job(id: Int) -> Job? { box.s.jobs.first { $0.id == id } }

    // ---- field (D-6)
    public func jobs(forCleaner id: Int, on day: Date) -> [Job] {
        let d = startOfDay(day)
        return box.s.jobs.filter { $0.state != "cancelled" && startOfDay($0.bookedStart) == d && $0.assignments.contains { $0.cleanerID == id } }
            .sorted { $0.bookedStart < $1.bookedStart }
    }

    static func assignment(_ s: State, _ cleanerID: Int, _ jobID: Int) throws -> (Int, Int) {
        guard let k = s.jobs.firstIndex(where: { $0.id == jobID }) else { throw CleaningError.notFound("job \(jobID)") }
        guard s.cleaners.contains(where: { $0.id == cleanerID }) else { throw CleaningError.notFound("cleaner \(cleanerID)") }
        guard let a = s.jobs[k].assignments.firstIndex(where: { $0.cleanerID == cleanerID }) else { throw CleaningError.wrongCleaner }
        return (k, a)
    }

    public func arrive(cleanerID: Int, jobID: Int, at t: Date) throws {
        try run { s in
            let (k, a) = try Store.assignment(s, cleanerID, jobID)
            guard ["scheduled", "in_progress"].contains(s.jobs[k].state), s.jobs[k].assignments[a].arrival == nil else {
                throw CleaningError.tapOutOfOrder("this cleaner can't arrive at this job now")
            }
            s.jobs[k].assignments[a].arrival = t
            s.jobs[k].state = "in_progress"
        }
    }

    public func depart(cleanerID: Int, jobID: Int, at t: Date) throws {
        try run { s in
            let (k, a) = try Store.assignment(s, cleanerID, jobID)
            guard let arr = s.jobs[k].assignments[a].arrival, s.jobs[k].assignments[a].departure == nil, t >= arr else {
                throw CleaningError.tapOutOfOrder("this cleaner can't depart from this job now")
            }
            s.jobs[k].assignments[a].departure = t
            s.jobs[k].assignments[a].workedMinutes = Int(t.timeIntervalSince(arr) / 60)
            if s.jobs[k].assignments.allSatisfy({ $0.departure != nil }) {
                let lines = s.jobs[k].assignments.sorted { $0.cleanerID < $1.cleanerID }.map {
                    InvoiceLine(cleanerID: $0.cleanerID, workedMinutes: $0.workedMinutes!, amount: cents(Decimal($0.workedMinutes!) / 60 * 45))
                }
                let inv = Invoice(id: s.newID("invoices"), jobID: jobID, issuedAt: t, lines: lines,
                                  total: lines.reduce(Decimal(0)) { $0 + $1.amount }, settled: false, paymentAmount: nil, paymentDate: nil)
                s.invoices.append(inv)
                s.jobs[k].state = "complete"; s.jobs[k].invoiceID = inv.id
            }
        }
    }

    // ---- extension (D-4)
    public func extend(cleanerID: Int, jobID: Int) throws {
        try run { s in
            let (k, _) = try Store.assignment(s, cleanerID, jobID)
            guard ["scheduled", "in_progress"].contains(s.jobs[k].state) else { throw CleaningError.tapOutOfOrder("job \(jobID) is \(s.jobs[k].state)") }
            s.jobs[k].bookedEnd = at(s.jobs[k].bookedEnd, 20)
            let d = startOfDay(s.jobs[k].bookedStart), floor = minute(s.jobs[k].bookedStart) + Int(s.jobs[k].bookedEnd.timeIntervalSince(s.jobs[k].bookedStart) / 60) + gap
            let mine = s.jobs[k].bookedStart
            let bumped = s.jobs.indices.filter {
                let j = s.jobs[$0]
                return j.id != jobID && j.state == "scheduled" && j.assignments.contains { $0.cleanerID == cleanerID }
                    && startOfDay(j.bookedStart) == d && minute(j.bookedStart) < floor && j.bookedStart >= mine
            }.sorted { s.jobs[$0].bookedStart < s.jobs[$1].bookedStart }
            for b in bumped { s.jobs[b].assignments = [] }
            for b in bumped { try Store.place(&s, b, from: d, floor: (d, floor)) }
        }
    }

    // ---- billing (D-7)
    public func invoice(forJob id: Int) -> Invoice? { box.s.invoices.first { $0.jobID == id } }

    public func recordPayment(invoiceID: Int, amount: Decimal, at t: Date) throws {
        try run { s in
            guard let i = s.invoices.firstIndex(where: { $0.id == invoiceID }) else { throw CleaningError.notFound("invoice \(invoiceID)") }
            if s.invoices[i].settled { throw CleaningError.alreadySettled }
            if amount != s.invoices[i].total { throw CleaningError.paymentAmountMismatch }
            s.invoices[i].settled = true; s.invoices[i].paymentAmount = amount; s.invoices[i].paymentDate = t
        }
    }

    // ---- utilization (D-8)
    public func utilizationReports(day: Date) -> [UtilizationReport] {
        let d = startOfDay(day), wd = cal.component(.weekday, from: d)
        let mon = addDays(d, -((wd + 5) % 7)), next = addDays(mon, 7)
        return box.s.cleaners.map { c in
            var dm = 0, wm = 0
            for j in box.s.jobs { for a in j.assignments where a.cleanerID == c.id {
                guard let dep = a.departure, let w = a.workedMinutes else { continue }
                let dd = startOfDay(dep)
                if dd == d { dm += w }
                if dd >= mon && dd < next { wm += w }
            } }
            return UtilizationReport(cleanerID: c.id, dayWorkedMinutes: dm, weekWorkedMinutes: wm)
        }
    }
}
