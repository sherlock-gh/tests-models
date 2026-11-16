import Foundation

/// The cleaner app's logic (contracts/operations.md, interfaces.md). Each change runs on a copy
/// of the data and is saved before it replaces it: an error changes nothing.
public final class CleaningService {
    static let dayStart = 480, dayEnd = 1020, gap = 60, maxLength = 540, searchDays = 366

    private let url: URL
    private var state: State

    public init(storeURL: URL) throws {
        url = storeURL
        if FileManager.default.fileExists(atPath: url.path) {
            state = try JSONDecoder().decode(State.self, from: Data(contentsOf: url))
        } else {
            state = State()
        }
    }

    private func change<T>(_ body: (inout State) throws -> T) throws -> T {
        var s = state
        let out = try body(&s)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try JSONEncoder().encode(s).write(to: url, options: .atomic)
        state = s
        return out
    }

    private static func fail(_ code: String, _ message: String) -> CleaningError { CleaningError(code: code, message: message) }

    private static func name(_ n: String) throws -> String {
        let t = n.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { throw fail("invalid_input", "name is required") }
        return t
    }

    private static func day(_ s: String) throws -> Int {
        guard let d = Calendar0.days(s) else { throw fail("invalid_input", "\(s) is not a date YYYY-MM-DD") }
        return d
    }

    private static func index<T>(_ xs: [T], _ id: Int, _ key: (T) -> Int, _ what: String) throws -> Int {
        guard let i = xs.firstIndex(where: { key($0) == id }) else { throw fail("not_found", "no \(what) \(id)") }
        return i
    }

    // MARK: cleaners

    public func createCleaner(name: String) throws -> Cleaner {
        try change { s in
            let c = Cleaner(id: s.newId("cleaner"), name: try Self.name(name))
            s.cleaners.append(c)
            return c
        }
    }

    public func updateCleaner(id: Int, name: String) throws -> Cleaner {
        try change { s in
            let i = try Self.index(s.cleaners, id, { $0.id }, "cleaner")
            s.cleaners[i].name = try Self.name(name)
            return s.cleaners[i]
        }
    }

    public func deleteCleaner(id: Int) throws {
        try change { s in
            s.cleaners.remove(at: try Self.index(s.cleaners, id, { $0.id }, "cleaner"))
            let mine = s.jobs.indices.filter { s.jobs[$0].status == "booked" && s.jobs[$0].cleanerIds.contains(id) }
                .sorted { (s.jobs[$0].date, s.jobs[$0].startMinute) < (s.jobs[$1].date, s.jobs[$1].startMinute) }
            for i in mine {
                s.jobs[i].cleanerIds = []
                try Self.place(&s, i, from: try Self.day(s.jobs[i].requestedDate), floor: nil)
            }
        }
    }

    public func getCleaner(id: Int) throws -> Cleaner { state.cleaners[try Self.index(state.cleaners, id, { $0.id }, "cleaner")] }
    public func listCleaners() -> [Cleaner] { state.cleaners }

    // MARK: clients

    public func createClient(name: String, address: String?) throws -> Client {
        try change { s in
            let c = Client(id: s.newId("client"), name: try Self.name(name), address: address)
            s.clients.append(c)
            return c
        }
    }

    public func updateClient(id: Int, name: String, address: String?) throws -> Client {
        try change { s in
            let i = try Self.index(s.clients, id, { $0.id }, "client")
            s.clients[i].name = try Self.name(name)
            s.clients[i].address = address
            return s.clients[i]
        }
    }

    public func deleteClient(id: Int) throws {
        try change { s in
            s.clients.remove(at: try Self.index(s.clients, id, { $0.id }, "client"))
            for i in s.jobs.indices where s.jobs[i].clientId == id && s.jobs[i].status == "booked" {
                s.jobs[i].status = "cancelled"
            }
        }
    }

    public func getClient(id: Int) throws -> Client { state.clients[try Self.index(state.clients, id, { $0.id }, "client")] }
    public func listClients() -> [Client] { state.clients }

    // MARK: booking

    private static func check(_ needed: Int, _ length: Int) throws {
        guard (1...3).contains(needed) else { throw fail("invalid_input", "cleanersNeeded must be 1, 2 or 3") }
        guard length > 0 && length <= maxLength else { throw fail("invalid_input", "lengthMinutes must be more than 0 and at most 540") }
    }

    private static func free(_ s: State, _ c: Int, _ date: String, _ start: Int, _ end: Int, skip: Int) -> Bool {
        for j in s.jobs where j.id != skip && j.status != "cancelled" && j.date == date && j.cleanerIds.contains(c) {
            if !(j.endMinute + gap <= start || j.startMinute >= end + gap) { return false }
        }
        return true
    }

    /// Books job `i` (its cleaners already cleared) into the earliest slot on or after `from`;
    /// `floor` (day, minute) bounds it from below on that day. Lowest-id free cleaners.
    private static func place(_ s: inout State, _ i: Int, from: Int, floor: (Int, Int)?) throws {
        let job = s.jobs[i]
        let ids = s.cleaners.map { $0.id }.sorted()
        if job.cleanersNeeded > ids.count {
            throw fail("unschedulable", "job \(job.id) needs \(job.cleanersNeeded) cleaners; there are \(ids.count)")
        }
        var d = from
        while Calendar0.weekday(d) >= 5 { d += 1 }
        for _ in 0..<searchDays {
            let date = Calendar0.string(d)
            let lo = floor.map { $0.0 == d ? $0.1 : dayStart } ?? dayStart
            var cands = Set([dayStart, lo])
            for j in s.jobs where j.id != job.id && j.status != "cancelled" && j.date == date { cands.insert(j.endMinute + gap) }
            for start in cands.filter({ $0 >= lo && $0 >= dayStart }).sorted() {
                if start + job.lengthMinutes > dayEnd { break }
                let ok = ids.filter { free(s, $0, date, start, start + job.lengthMinutes, skip: job.id) }
                if ok.count >= job.cleanersNeeded {
                    let chosen = Array(ok.prefix(job.cleanersNeeded))
                    s.jobs[i].date = date
                    s.jobs[i].startMinute = start
                    s.jobs[i].endMinute = start + job.lengthMinutes
                    s.jobs[i].cleanerIds = chosen
                    s.jobs[i].timeEntries = chosen.map { TimeEntry(cleanerId: $0, arrivedAt: nil, departedAt: nil, secondsWorked: nil) }
                    return
                }
            }
            d += 1
            while Calendar0.weekday(d) >= 5 { d += 1 }
        }
        throw fail("unschedulable", "no slot for job \(job.id)")
    }

    public func bookJob(clientId: Int, cleanersNeeded: Int, lengthMinutes: Int, requestedDate: String) throws -> Job {
        try change { s in
            _ = try Self.index(s.clients, clientId, { $0.id }, "client")
            try Self.check(cleanersNeeded, lengthMinutes)
            let from = try Self.day(requestedDate)
            s.jobs.append(Job(id: s.newId("job"), clientId: clientId, cleanersNeeded: cleanersNeeded, lengthMinutes: lengthMinutes,
                              requestedDate: requestedDate, date: "", startMinute: 0, endMinute: 0, cleanerIds: [],
                              status: "booked", timeEntries: []))
            try Self.place(&s, s.jobs.count - 1, from: from, floor: nil)
            return s.jobs[s.jobs.count - 1]
        }
    }

    public func updateJob(id: Int, clientId: Int?, cleanersNeeded: Int?, lengthMinutes: Int?, requestedDate: String?) throws -> Job {
        try change { s in
            let i = try Self.index(s.jobs, id, { $0.id }, "job")
            guard s.jobs[i].status == "booked" else { throw Self.fail("invalid_state", "job \(id) has started or ended") }
            if let c = clientId { _ = try Self.index(s.clients, c, { $0.id }, "client"); s.jobs[i].clientId = c }
            let n = cleanersNeeded ?? s.jobs[i].cleanersNeeded, l = lengthMinutes ?? s.jobs[i].lengthMinutes
            try Self.check(n, l)
            if let r = requestedDate { _ = try Self.day(r); s.jobs[i].requestedDate = r }
            s.jobs[i].cleanersNeeded = n
            s.jobs[i].lengthMinutes = l
            s.jobs[i].cleanerIds = []
            try Self.place(&s, i, from: try Self.day(s.jobs[i].requestedDate), floor: nil)
            return s.jobs[i]
        }
    }

    public func deleteJob(id: Int) throws {
        try change { s in
            let i = try Self.index(s.jobs, id, { $0.id }, "job")
            guard s.jobs[i].status == "booked" else { throw Self.fail("invalid_state", "job \(id) has started or ended") }
            s.jobs.remove(at: i)
        }
    }

    public func getJob(id: Int) throws -> Job { state.jobs[try Self.index(state.jobs, id, { $0.id }, "job")] }
    public func listJobs() -> [Job] { state.jobs }

    public func cleanerDay(cleanerId: Int, date: String) throws -> [Job] {
        _ = try Self.index(state.cleaners, cleanerId, { $0.id }, "cleaner")
        _ = try Self.day(date)
        return state.jobs.filter { $0.date == date && $0.cleanerIds.contains(cleanerId) && $0.status != "cancelled" }
            .sorted { $0.startMinute < $1.startMinute }
    }

    // MARK: field

    private static func entry(_ s: State, _ jobId: Int, _ cleanerId: Int) throws -> (Int, Int) {
        let i = try index(s.jobs, jobId, { $0.id }, "job")
        if s.jobs[i].status == "complete" || s.jobs[i].status == "cancelled" {
            throw fail("invalid_state", "job \(jobId) is \(s.jobs[i].status)")
        }
        guard let e = s.jobs[i].timeEntries.firstIndex(where: { $0.cleanerId == cleanerId }) else {
            throw fail("invalid_input", "cleaner \(cleanerId) is not assigned to job \(jobId)")
        }
        return (i, e)
    }

    public func arrive(jobId: Int, cleanerId: Int, timestamp: String) throws -> Job {
        try change { s in
            let (i, e) = try Self.entry(s, jobId, cleanerId)
            guard Calendar0.seconds(timestamp) != nil else { throw Self.fail("invalid_input", "timestamp must be YYYY-MM-DDTHH:MM:SS") }
            if s.jobs[i].timeEntries[e].arrivedAt != nil { throw Self.fail("invalid_state", "already arrived") }
            s.jobs[i].timeEntries[e].arrivedAt = timestamp
            s.jobs[i].status = "in_progress"
            return s.jobs[i]
        }
    }

    public func depart(jobId: Int, cleanerId: Int, timestamp: String) throws -> Job {
        try change { s in
            let (i, e) = try Self.entry(s, jobId, cleanerId)
            guard let t = Calendar0.seconds(timestamp) else { throw Self.fail("invalid_input", "timestamp must be YYYY-MM-DDTHH:MM:SS") }
            guard let a = s.jobs[i].timeEntries[e].arrivedAt else { throw Self.fail("invalid_state", "has not arrived") }
            if s.jobs[i].timeEntries[e].departedAt != nil { throw Self.fail("invalid_state", "already departed") }
            let secs = t - Calendar0.seconds(a)!
            if secs < 0 { throw Self.fail("invalid_input", "departure is before arrival") }
            s.jobs[i].timeEntries[e].departedAt = timestamp
            s.jobs[i].timeEntries[e].secondsWorked = secs
            if s.jobs[i].timeEntries.allSatisfy({ $0.departedAt != nil }) {
                s.jobs[i].status = "complete"
                let job = s.jobs[i]
                let lines = job.timeEntries.sorted { $0.cleanerId < $1.cleanerId }.map { x in
                    InvoiceLine(cleanerId: x.cleanerId, cleanerName: s.cleaners.first { $0.id == x.cleanerId }?.name ?? "",
                                secondsWorked: x.secondsWorked!, chargeCents: (x.secondsWorked! * 5 + 2) / 4)
                }
                s.invoices.append(Invoice(id: s.newId("invoice"), jobId: job.id,
                                          clientName: s.clients.first { $0.id == job.clientId }?.name ?? "",
                                          lines: lines, totalCents: lines.reduce(0) { $0 + $1.chargeCents }, settled: false))
            }
            return s.jobs[i]
        }
    }

    public func requestExtension(jobId: Int, cleanerId: Int, minutes: Int) throws -> Job {
        try change { s in
            let (i, _) = try Self.entry(s, jobId, cleanerId)
            guard minutes > 0 && minutes % 20 == 0 else { throw Self.fail("invalid_input", "minutes must be a positive multiple of 20") }
            s.jobs[i].endMinute += minutes
            let j = s.jobs[i], floor = j.endMinute + Self.gap
            let bumped = s.jobs.indices.filter { k in
                let x = s.jobs[k]
                return x.id != j.id && x.status == "booked" && x.date == j.date && !Set(x.cleanerIds).isDisjoint(with: j.cleanerIds)
                    && x.startMinute >= j.startMinute && x.startMinute < floor
            }.sorted { s.jobs[$0].startMinute < s.jobs[$1].startMinute }
            for k in bumped { s.jobs[k].cleanerIds = [] }
            let day = try Self.day(j.date)
            for k in bumped { try Self.place(&s, k, from: day, floor: (day, floor)) }
            return s.jobs[i]
        }
    }

    // MARK: invoices

    public func listInvoices(settled: Bool?) -> [Invoice] { state.invoices.filter { settled == nil || $0.settled == settled } }
    public func getInvoice(id: Int) throws -> Invoice { state.invoices[try Self.index(state.invoices, id, { $0.id }, "invoice")] }

    public func payInvoice(id: Int, amountCents: Int) throws -> Invoice {
        try change { s in
            let i = try Self.index(s.invoices, id, { $0.id }, "invoice")
            if s.invoices[i].settled { throw Self.fail("invalid_state", "invoice \(id) is settled already") }
            if amountCents != s.invoices[i].totalCents {
                throw Self.fail("payment_mismatch", "payment must be exactly \(s.invoices[i].totalCents) cents")
            }
            s.invoices[i].settled = true
            s.payments.append(Payment(invoiceId: id, amountCents: amountCents))
            return s.invoices[i]
        }
    }

    // MARK: utilization

    public func utilization(cleanerId: Int, date: String) throws -> Utilization {
        _ = try Self.index(state.cleaners, cleanerId, { $0.id }, "cleaner")
        let d = try Self.day(date), monday = d - Calendar0.weekday(d)
        var ds = 0, ws = 0
        for j in state.jobs {
            for e in j.timeEntries where e.cleanerId == cleanerId {
                guard let secs = e.secondsWorked, let a = e.arrivedAt, let at = Calendar0.seconds(a) else { continue }
                let ad = Int((Double(at) / 86400).rounded(.down))
                if ad == d { ds += secs }
                if ad >= monday && ad <= monday + 6 { ws += secs }
            }
        }
        return Utilization(cleanerId: cleanerId, date: date, daySeconds: ds, weekSeconds: ws,
                           dayPercent: Double(ds) / 28800 * 100, weekPercent: Double(ws) / 144000 * 100)
    }
}
