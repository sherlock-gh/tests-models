import Foundation

extension CleaningApp {
    public func daySchedule(cleanerId: Int, on day: Day) -> [DayPart] {
        state.jobs.filter { $0.status == "booked" }.flatMap { j in j.parts.filter { $0.day == day && $0.assignments.contains { $0.cleanerId == cleanerId } }.map { p in DayPart(jobId: j.id, part: p, client: state.clients.first { $0.id == j.clientId }, coWorkers: p.assignments.map(\.cleanerId).filter { $0 != cleanerId }) } }
    }
    func locate(_ job: Job, cleaner: Int, at: Date) throws -> (Int, Int) {
        let date = String(format(at).prefix(10))
        guard let pi = job.parts.firstIndex(where: { $0.day == date && $0.assignments.contains { $0.cleanerId == cleaner } }) ?? job.parts.firstIndex(where: { $0.assignments.contains { $0.cleanerId == cleaner && $0.depart == nil } }), let ai = job.parts[pi].assignments.firstIndex(where: { $0.cleanerId == cleaner }) else { throw missing("cleaner not assigned") }
        return (pi, ai)
    }
    public func arrive(jobId: Int, cleanerId: Int, at: Date) throws -> Job {
        try change { s in
            guard let ji = s.jobs.firstIndex(where: { $0.id == jobId }) else { throw missing("job not found") }
            guard s.jobs[ji].status == "booked" else { throw conflict("cancelled job") }
            let (pi, ai) = try locate(s.jobs[ji], cleaner: cleanerId, at: at)
            guard s.jobs[ji].parts[pi].assignments[ai].arrive == nil else { throw conflict("already arrived") }
            s.jobs[ji].parts[pi].assignments[ai].arrive = format(at)
            return s.jobs[ji]
        }
    }
    public func depart(jobId: Int, cleanerId: Int, at: Date) throws -> JobWithInvoice? {
        try change { s in
            guard let ji = s.jobs.firstIndex(where: { $0.id == jobId }) else { throw missing("job not found") }
            guard s.jobs[ji].status == "booked" else { throw conflict("cancelled job") }
            let (pi, ai) = try locate(s.jobs[ji], cleaner: cleanerId, at: at)
            let a = s.jobs[ji].parts[pi].assignments[ai]
            guard let arrived = a.arrive, let instant = parse(arrived), a.depart == nil, at >= instant else { throw conflict("depart requires arrive and must follow it") }
            s.jobs[ji].parts[pi].assignments[ai].depart = format(at)
            var invoice: Invoice?
            if s.jobs[ji].invoiceId == nil && s.jobs[ji].parts.allSatisfy({ $0.assignments.allSatisfy { $0.depart != nil } }) {
                let job = s.jobs[ji]
                let ids = Set(job.parts.flatMap { $0.assignments.map(\.cleanerId) }).sorted()
                let lines = ids.map { cid -> InvoiceLine in
                    let minutes = job.parts.flatMap(\.assignments).filter { $0.cleanerId == cid }.reduce(0) { sum, a in
                        guard let start = a.arrive.flatMap(parse), let end = a.depart.flatMap(parse) else { return sum }
                        return sum + Int(end.timeIntervalSince(start) / 60)
                    }
                    return InvoiceLine(cleanerId: cid, cleanerName: s.cleaners.first { $0.id == cid }?.name ?? "Cleaner \(cid)", minutesWorked: minutes, amountCents: (minutes * 4500 + 30) / 60)
                }
                invoice = Invoice(id: s.issue("invoices"), jobId: jobId, issuedAt: format(at), lines: lines, totalCents: lines.reduce(0) { $0 + $1.amountCents }, settled: false, payment: nil)
                s.invoices.append(invoice!); s.jobs[ji].invoiceId = invoice!.id
            }
            return JobWithInvoice(job: s.jobs[ji], invoice: invoice)
        }
    }
    public func listInvoices(settled: Bool? = nil) -> [Invoice] { state.invoices.filter { settled == nil || $0.settled == settled } }
    public func readInvoice(id: Int) throws -> Invoice { guard let invoice = state.invoices.first(where: { $0.id == id }) else { throw missing("invoice not found") }; return invoice }
    public func recordPayment(invoiceId: Int, amountCents: Int) throws -> Invoice {
        try change { s in
            guard let i = s.invoices.firstIndex(where: { $0.id == invoiceId }) else { throw missing("invoice not found") }
            guard !s.invoices[i].settled && s.invoices[i].totalCents == amountCents else { throw conflict("payment must equal total and be made once") }
            s.invoices[i].settled = true; s.invoices[i].payment = Payment(amountCents: amountCents, paidAt: format(now()))
            return s.invoices[i]
        }
    }
}
