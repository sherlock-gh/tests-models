// Milestone 2 (Flash-Next's iteration 3 plan): the cleaner's day, Arrive and Depart, invoices (US2)
// and settlement (US5).
import Foundation
import Testing
import CleaningKit

// Taps are milestone 2's, so their helpers live here (M1.swift must compile against milestone 1 alone)
extension Fixture {
    func arrive(_ job: Int, _ c: Int, _ day: String, _ hm: String) throws -> Job { try store.arrive(jobId: job, cleanerId: c, atInstant: TT.at(day, hm)) }
    func depart(_ job: Int, _ c: Int, _ day: String, _ hm: String) throws -> Job { try store.depart(jobId: job, cleanerId: c, atInstant: TT.at(day, hm)) }
}

@Test func theCleanersDay() throws {
    let f = try Fixture()
    let cs = try f.cleaners(2), cl = try f.client()
    let j1 = try f.book(cl, 1, 240, MON), j2 = try f.book(cl, 1, 240, MON), j3 = try f.book(cl, 1, 120, MON)
    _ = try f.book(cl, 1, 60, TUE)
    var all = [Int]()
    for c in cs {
        let mine = try f.store.jobsForToday(cleanerId: c, on: TT.day(MON))
        all += mine.map(\.id)
        #expect(mine.map { $0.parts[0].start } == mine.map { $0.parts[0].start }.sorted())
    }
    #expect(all.sorted() == [j1.id, j2.id, j3.id].sorted())
    _ = f.refused([], "an unknown cleaner's day") { _ = try f.store.jobsForToday(cleanerId: 9999, on: TT.day(MON)) }
}

@Test func aSplitJobIsOnEachOfItsDays() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 600, MON)
    for d in [MON, TUE] { #expect(try f.store.jobsForToday(cleanerId: a, on: TT.day(d)).map(\.id) == [j.id]) }
}

@Test func arriveAndDepart() throws {
    let f = try Fixture()
    let cs = try f.cleaners(2)
    let j = try f.book(try f.client(), 2, 240, MON)
    var x = try f.arrive(j.id, cs[0], MON, "08:02")
    #expect(x.status == .inProgress)
    #expect(x.taps.map { "\($0.cleanerId) \($0.kind.rawValue) \(TT.string($0.instant))" } == ["\(cs[0]) arrive \(MON)T08:02"])
    x = try f.depart(j.id, cs[0], MON, "10:02")
    #expect(x.status == .inProgress && x.invoiceId == nil && x.invoice == nil && f.store.invoices().isEmpty)
    #expect(x.taps.last.map { "\($0.kind.rawValue) \(TT.string($0.instant))" } == "depart \(MON)T10:02")
}

@Test func tapsOutOfOrderChangeNothing() throws {
    // G11, G12, and taps that aren't the cleaner's
    let f = try Fixture()
    let cs = try f.cleaners(3)
    let j = try f.book(try f.client(), 2, 240, MON)
    let on = j.cleanerIds, off = cs.first { !j.cleanerIds.contains($0) }!
    _ = f.refused([j.id], "Depart with no Arrive") { _ = try f.depart(j.id, on[0], MON, "09:00") }
    _ = f.refused([j.id], "a cleaner not on the job") { _ = try f.arrive(j.id, off, MON, "08:00") }
    _ = f.refused([j.id], "an unknown job") { _ = try f.arrive(9999, on[0], MON, "08:00") }
    _ = try f.arrive(j.id, on[0], MON, "08:00")
    _ = f.refused([j.id], "a second Arrive") { _ = try f.arrive(j.id, on[0], MON, "08:05") }
}

@Test func aLineIsBilledToTheMinute() throws {
    // G7: Arrive 9:00, Depart 12:30 -> 15750 cents
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 240, MON)
    _ = try f.arrive(j.id, a, MON, "09:00")
    let x = try f.depart(j.id, a, MON, "12:30")
    let inv = try #require(x.invoice)
    #expect(x.status == .complete && x.invoiceId == inv.id)
    #expect(inv.lines.map { "\($0.cleanerId) \($0.minutesWorked) \($0.cents)" } == ["\(a) 210 15750"])
    #expect(inv.totalCents == 15750 && TT.string(inv.issuedAt) == "\(MON)T12:30" && inv.jobId == j.id && !inv.settled)
}

@Test func theInvoiceIssuesOnTheLastDeparture() throws {
    // G8: 210 min and 240 min on one invoice -> 15750 + 18000 = 33750 cents
    let f = try Fixture()
    let cs = try f.cleaners(2)
    let j = try f.book(try f.client(), 2, 240, MON)
    _ = try f.arrive(j.id, cs[0], MON, "08:00")
    _ = try f.arrive(j.id, cs[1], MON, "08:00")
    #expect(try f.depart(j.id, cs[1], MON, "11:30").invoice == nil)
    #expect(f.store.invoices().isEmpty)
    let x = try f.depart(j.id, cs[0], MON, "12:00")
    let inv = try #require(f.store.invoices().first)
    #expect(f.store.invoices().count == 1 && x.invoice.map(describe) == describe(inv) && x.invoiceId == inv.id && x.status == .complete)
    #expect(inv.lines.map { "\($0.cleanerId) \($0.minutesWorked) \($0.cents)" }.sorted() == ["\(cs[0]) 240 18000", "\(cs[1]) 210 15750"].sorted())
    #expect(inv.totalCents == 33750 && TT.string(inv.issuedAt) == "\(MON)T12:00")
    #expect(describe(try f.store.invoice(id: inv.id)) == describe(inv))
    _ = f.refused([j.id], "Arrive on a complete job") { _ = try f.arrive(j.id, cs[0], MON, "13:00") }
}

@Test func aSplitJobIsBilledWhenItsLastPartEnds() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 600, MON)
    _ = try f.arrive(j.id, a, MON, "08:00")
    let x = try f.depart(j.id, a, MON, "16:00")
    #expect(x.status == .inProgress && f.store.invoices().isEmpty)
    _ = try f.arrive(j.id, a, TUE, "08:00")
    let y = try f.depart(j.id, a, TUE, "10:00")
    let inv = try #require(y.invoice)
    #expect(inv.lines.map { "\($0.minutesWorked) \($0.cents)" } == ["600 45000"])
    #expect(TT.string(inv.issuedAt) == "\(TUE)T10:00" && y.status == .complete)
}

@Test func settlement() throws {
    // G18, G19, G20
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 240, MON)
    _ = try f.arrive(j.id, a, MON, "08:00")
    let inv = try #require(try f.depart(j.id, a, MON, "11:23").invoice)    // 203 min: 15225 cents
    #expect(inv.totalCents == 15225)
    for amount in [15224, 15226, 10000] {
        _ = f.refused([j.id], "paying \(amount)") { _ = try f.store.pay(invoiceId: inv.id, amountCents: amount) }
    }
    _ = f.refused([j.id], "paying an unknown invoice") { _ = try f.store.pay(invoiceId: 9999, amountCents: 100) }
    #expect(f.store.invoices().map(\.settled) == [false])
    let paid = try f.store.pay(invoiceId: inv.id, amountCents: 15225)
    #expect(paid.settled && paid.totalCents == 15225)
    _ = f.refused([j.id], "paying a settled invoice") { _ = try f.store.pay(invoiceId: inv.id, amountCents: 15225) }
    _ = f.refused([j.id], "changing an invoice") { _ = try f.store.updateInvoice(id: inv.id, totalCents: 1) }
    _ = f.refused([j.id], "deleting an invoice") { try f.store.deleteInvoice(id: inv.id) }
    #expect(f.store.invoices().map(\.settled) == [true])
}

@Test func invoicesSurviveReopening() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 60, MON)
    _ = try f.arrive(j.id, a, MON, "08:00")
    let inv = try #require(try f.depart(j.id, a, MON, "09:00").invoice)
    _ = try f.store.pay(invoiceId: inv.id, amountCents: 4500)
    let before = f.store.invoices().map(describe)
    try f.reopen()
    let again = try f.job(j.id)
    #expect(f.store.invoices().map(describe) == before && again.status == .complete)
}
