import Foundation

extension CleaningApp {
    func rebook(_ s: inout State, id: Int, floor: Date? = nil) throws {
        guard let i = s.jobs.firstIndex(where: { $0.id == id }) else { throw missing("job not found") }
        let original = s.jobs.remove(at: i)
        guard future(original) else { throw conflict("cannot rebook arrived job") }
        var result = original
        result.parts = try place(s, requested: original.requestedDay, durations: lengths(original.expectedLengthHours), needed: original.cleanersNeeded, floor: floor)
        s.jobs.append(result)
    }
    public func extend(jobId: Int, cleanerId: Int, minutes: Int = 20, at: Date) throws -> ExtensionResult {
        guard minutes == 20 else { throw bad("extension must be a 20-minute step") }
        return try change { s in
            guard let ji = s.jobs.firstIndex(where: { $0.id == jobId }) else { throw missing("job not found") }
            let (pi, ai) = try locate(s.jobs[ji], cleaner: cleanerId, at: at)
            let a = s.jobs[ji].parts[pi].assignments[ai]
            guard let arrived = a.arrive.flatMap(parse), arrived <= at, a.depart == nil else { throw conflict("extension requires arrived cleaner not departed") }
            s.jobs[ji].parts[pi].assignments[ai].extendedMinutes += 20
            let part = s.jobs[ji].parts[pi]
            let cutoff = parse(part.end)!.addingTimeInterval(Double((a.extendedMinutes + 80) * 60))
            let start = parse(part.start)!
            let crew = Set(part.assignments.map(\.cleanerId))
            let bumped = s.jobs.filter { j in j.id != jobId && j.status == "booked" && j.parts.contains { p in
                guard let ps = parse(p.start) else { return false }
                return ps >= start && ps < cutoff && p.assignments.contains { crew.contains($0.cleanerId) }
            } }.sorted { $0.parts[0].start < $1.parts[0].start }.map(\.id)
            for id in bumped { guard let index = s.jobs.firstIndex(where: { $0.id == id }), future(s.jobs[index]) else { throw conflict("cannot bump arrived job") } }
            let originals = s.jobs.filter { bumped.contains($0.id) }
            s.jobs.removeAll { bumped.contains($0.id) }
            for original in originals {
                var moved = original
                moved.parts = try place(s, requested: original.requestedDay, durations: lengths(original.expectedLengthHours), needed: original.cleanersNeeded, floor: cutoff)
                s.jobs.append(moved)
            }
            return ExtensionResult(job: s.jobs.first { $0.id == jobId }!, rebookedJobIds: bumped)
        }
    }
    public func deleteCleaner(id: Int) throws -> RebookedJobs {
        try change { s in
            guard s.cleaners.contains(where: { $0.id == id }) else { throw missing("cleaner not found") }
            let affected = s.jobs.filter { $0.status == "booked" && future($0) && $0.parts.contains { $0.assignments.contains { $0.cleanerId == id } } }.sorted { $0.parts[0].start < $1.parts[0].start }
            s.cleaners.removeAll { $0.id == id }
            s.jobs.removeAll { j in affected.contains { $0.id == j.id } }
            for original in affected {
                var moved = original
                moved.parts = try place(s, requested: original.requestedDay, durations: lengths(original.expectedLengthHours), needed: original.cleanersNeeded)
                s.jobs.append(moved)
            }
            return RebookedJobs(rebookedJobIds: affected.map(\.id))
        }
    }
    public func deleteClient(id: Int) throws -> CancelledJobs {
        try change { s in
            guard s.clients.contains(where: { $0.id == id }) else { throw missing("client not found") }
            var affected: [Int] = []
            for i in s.jobs.indices where s.jobs[i].clientId == id && s.jobs[i].status == "booked" && future(s.jobs[i]) {
                affected.append(s.jobs[i].id); s.jobs[i].status = "cancelled"
            }
            s.clients.removeAll { $0.id == id }; return CancelledJobs(cancelledJobIds: affected)
        }
    }
    public func deleteJob(id: Int) throws {
        try change { s in
            guard let index = s.jobs.firstIndex(where: { $0.id == id }) else { throw missing("job not found") }
            guard s.jobs[index].invoiceId == nil else { throw conflict("invoice issued") }
            s.jobs.remove(at: index)
        }
    }
    public func updateJob(id: Int, clientId: Int, cleanersNeeded: Int, expectedLengthHours: Double, requestedDay: Day) throws -> Job {
        guard state.clients.contains(where: { $0.id == clientId }) else { throw missing("client not found") }
        guard (1...3).contains(cleanersNeeded), dayDate(requestedDay) != nil else { throw bad("invalid job") }
        let durations = try lengths(expectedLengthHours)
        return try change { s in
            guard let i = s.jobs.firstIndex(where: { $0.id == id }) else { throw missing("job not found") }
            let old = s.jobs.remove(at: i)
            guard old.invoiceId == nil && future(old) && old.status == "booked" else { throw conflict("cannot edit started or invoiced job") }
            guard requestedDay <= old.parts[0].day else { throw conflict("requested day exceeds existing booking") }
            var modified = old
            for index in 0..<min(modified.parts.count, durations.count) {
                let p = modified.parts[index], start = parse(p.start)!
                let end = start.addingTimeInterval(Double(durations[index] * 60))
                guard format(end) <= p.day + "T17:00" else { throw conflict("edited part exceeds workday") }
                var selected = p.assignments.prefix(cleanersNeeded).map(\.cleanerId)
                guard selected.allSatisfy({ free(s, cleaner: $0, start: start, end: end) }) else { throw conflict("edited job overlaps a booking") }
                if selected.count < cleanersNeeded {
                    for cid in s.cleaners.map(\.id).sorted() where !selected.contains(cid) && free(s, cleaner: cid, start: start, end: end) {
                        selected.append(cid)
                        if selected.count == cleanersNeeded { break }
                    }
                }
                guard selected.count == cleanersNeeded else { throw conflict("not enough free cleaners for edited job") }
                modified.parts[index].end = format(end)
                modified.parts[index].assignments = selected.map { Assignment(cleanerId: $0, arrive: nil, depart: nil, extendedMinutes: 0) }
            }
            if durations.count < modified.parts.count { modified.parts.removeLast(modified.parts.count - durations.count) }
            if durations.count > modified.parts.count {
                let count = modified.parts.count
                let previous = modified.parts.last!.day
                let extras = try place(s, requested: requestedDay, durations: Array(durations[count...]), needed: cleanersNeeded,
                                       preferred: modified.parts[0].assignments.map(\.cleanerId), startDay: addDays(previous, 1))
                for (index, var extra) in extras.enumerated() { extra.partIndex = count + index; modified.parts.append(extra) }
            }
            modified.clientId = clientId; modified.cleanersNeeded = cleanersNeeded
            modified.expectedLengthHours = expectedLengthHours; modified.requestedDay = requestedDay
            s.jobs.append(modified); return modified
        }
    }
}
