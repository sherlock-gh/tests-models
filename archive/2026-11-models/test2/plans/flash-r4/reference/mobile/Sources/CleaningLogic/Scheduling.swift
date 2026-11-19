import Foundation

extension CleaningApp {
    public func createCleaner(name: String, phone: String, email: String) throws -> Cleaner {
        try valid(name, phone, email)
        return try change { s in let c = Cleaner(id: s.issue("cleaners"), name: name, phone: phone, email: email, active: true); s.cleaners.append(c); return c }
    }
    public func readCleaner(id: Int) throws -> Cleaner { guard let c = state.cleaners.first(where: { $0.id == id }) else { throw missing("cleaner not found") }; return c }
    public func listCleaners() -> [Cleaner] { state.cleaners }
    public func updateCleaner(id: Int, name: String, phone: String, email: String) throws -> Cleaner {
        try valid(name, phone, email)
        return try change { s in guard let i = s.cleaners.firstIndex(where: { $0.id == id }) else { throw missing("cleaner not found") }; s.cleaners[i].name = name; s.cleaners[i].phone = phone; s.cleaners[i].email = email; return s.cleaners[i] }
    }
    public func createClient(name: String, address: String, phone: String) throws -> Client {
        try valid(name, address, phone)
        return try change { s in let c = Client(id: s.issue("clients"), name: name, address: address, phone: phone); s.clients.append(c); return c }
    }
    public func readClient(id: Int) throws -> Client { guard let c = state.clients.first(where: { $0.id == id }) else { throw missing("client not found") }; return c }
    public func listClients() -> [Client] { state.clients }
    public func updateClient(id: Int, name: String, address: String, phone: String) throws -> Client {
        try valid(name, address, phone)
        return try change { s in guard let i = s.clients.firstIndex(where: { $0.id == id }) else { throw missing("client not found") }; s.clients[i].name = name; s.clients[i].address = address; s.clients[i].phone = phone; return s.clients[i] }
    }
    public func readJob(id: Int) throws -> Job { guard let j = state.jobs.first(where: { $0.id == id }) else { throw missing("job not found") }; return j }
    public func listJobs(from: Day? = nil, to: Day? = nil, clientId: Int? = nil) -> [Job] {
        state.jobs.filter { j in (clientId == nil || j.clientId == clientId) && j.parts.contains { $0.day >= (from ?? "0000") && $0.day <= (to ?? "9999") } }
    }
    func lengths(_ hours: Double) throws -> [Int] {
        guard hours.isFinite && hours > 0 && hours < 1_000_000 else { throw bad("length must be positive") }
        let raw = hours * 60
        var remaining = Int(abs(raw - raw.rounded()) < 0.000001 ? raw.rounded() : raw.rounded(.up)), result: [Int] = []
        while remaining > 0 { let piece = min(480, remaining); result.append(piece); remaining -= piece }
        return result
    }
    func free(_ s: State, cleaner: Int, start: Date, end: Date) -> Bool {
        for j in s.jobs where j.status == "booked" {
            for p in j.parts { for a in p.assignments where a.cleanerId == cleaner {
                guard let lo = parse(p.start), let hi = parse(p.end) else { continue }
                let effective = hi.addingTimeInterval(Double(a.extendedMinutes * 60))
                if start < lo { if lo < end.addingTimeInterval(3600) { return false } }
                else if start < effective.addingTimeInterval(3600) { return false }
            } }
        }
        return true
    }
    func place(_ s: State, requested: Day, durations: [Int], needed: Int, floor: Date? = nil, preferred initial: [Int] = [], startDay: Day? = nil) throws -> [JobPart] {
        var parts: [JobPart] = [], preferred = initial, earliest = startDay ?? requested
        for (index, duration) in durations.enumerated() {
            var found: JobPart?
            for offset in 0...90 where found == nil {
                let d = addDays(requested, offset)
                if d < earliest { continue }
                guard let base = dayDate(d) else { continue }
                let weekday = calendar.component(.weekday, from: base)
                if weekday == 1 || weekday == 7 { continue }
                for step in 0..<36 {
                    let start = base.addingTimeInterval(Double(step * 900)), end = start.addingTimeInterval(Double(duration * 60))
                    if let floor, index == 0 && start < floor { continue }
                    if format(end) > d + "T17:00" { continue }
                    let choices = s.cleaners.map(\.id).sorted().filter { free(s, cleaner: $0, start: start, end: end) }
                    let selected = preferred.filter { choices.contains($0) } + choices.filter { !preferred.contains($0) }
                    if selected.count >= needed {
                        found = JobPart(partIndex: index, day: d, start: format(start), end: format(end), assignments: selected.prefix(needed).map { Assignment(cleanerId: $0, arrive: nil, depart: nil, extendedMinutes: 0) })
                        break
                    }
                }
            }
            guard let part = found else { throw conflict("No slot in 90 days") }
            parts.append(part)
            if index == 0 && preferred.isEmpty { preferred = part.assignments.map(\.cleanerId) }
            earliest = addDays(part.day, 1)
        }
        return parts
    }
    public func bookJob(clientId: Int, cleanersNeeded: Int, expectedLengthHours: Double, requestedDay: Day) throws -> Job {
        guard state.clients.contains(where: { $0.id == clientId }) else { throw missing("client not found") }
        guard (1...3).contains(cleanersNeeded), dayDate(requestedDay) != nil else { throw bad("invalid booking request") }
        let durations = try lengths(expectedLengthHours)
        return try change { s in
            let parts = try place(s, requested: requestedDay, durations: durations, needed: cleanersNeeded)
            let j = Job(id: s.issue("jobs"), clientId: clientId, cleanersNeeded: cleanersNeeded, expectedLengthHours: expectedLengthHours, requestedDay: requestedDay, status: "booked", parts: parts, invoiceId: nil)
            s.jobs.append(j); return j
        }
    }
}
