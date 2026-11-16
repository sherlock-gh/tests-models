// Milestone 2 (Flash-Next's plan): the cleaner's day, Arrive and Depart, invoices and settlement (US2, US3).
import Foundation
import Testing
import CleaningLogic

func T(_ hm: String, _ day: String = MON) -> Date { TestTime.at(day, hm) }

@Suite struct M2FieldAndBilling {
    @Test func cleanersDay() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2)
        let cl = try f.client()
        let j1 = try f.book(cl, 1, 4, MON), j2 = try f.book(cl, 1, 4, MON), j3 = try f.book(cl, 1, 2, MON)
        _ = try f.book(cl, 1, 1, TUE)
        #expect(same(f.store.jobs(forCleaner: ids[0], on: TestTime.day(MON)).map(\.id), [j1.id, j3.id]))
        #expect(same(f.store.jobs(forCleaner: ids[1], on: TestTime.day(MON)).map(\.id), [j2.id]))
    }

    @Test func arriveAndDepart() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2), (a, b) = (ids[0], ids[1])
        let j = try f.book(try f.client(), 2, 4, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:02"))
        var x = f.job(j.id)
        #expect(same(x.state, "in_progress"))
        var w = Dictionary(uniqueKeysWithValues: x.assignments.map { ($0.cleanerID, $0) })
        #expect(same(w[a]!.arrival, T("08:02")) && w[b]!.arrival == nil)
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("10:02"))
        x = f.job(j.id)
        w = Dictionary(uniqueKeysWithValues: x.assignments.map { ($0.cleanerID, $0) })
        #expect(same(w[a]!.departure, T("10:02")) && same(w[a]!.workedMinutes, 120) && same(x.state, "in_progress"))
        #expect(f.store.invoice(forJob: j.id) == nil)                   // b still working
    }

    @Test func tapsOutOfOrderChangeNothing() throws {
        let f = try Fixture()
        let ids = try f.cleaners(3), (a, c) = (ids[0], ids[2])
        let j = try f.book(try f.client(), 2, 4, MON)
        f.fails(["tapOutOfOrder"]) { try f.store.depart(cleanerID: a, jobID: j.id, at: T("09:00")) }
        f.fails(["wrongCleaner"]) { try f.store.arrive(cleanerID: c, jobID: j.id, at: T("08:00")) }
        f.fails(["notFound"]) { try f.store.arrive(cleanerID: a, jobID: 9999, at: T("08:00")) }
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        f.fails(["tapOutOfOrder"]) { try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:05")) }
        f.fails { try f.store.depart(cleanerID: a, jobID: j.id, at: T("07:59")) }       // before the arrival
    }

    @Test func invoiceOnTheLastDeparture() throws {
        // The plan's own example (US3-AC1): 4.0 h and 3.5 h -> $180.00 + $157.50 = $337.50
        let f = try Fixture()
        let ids = try f.cleaners(2), (a, b) = (ids[0], ids[1])
        let j = try f.book(try f.client(), 2, 4, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        try f.store.arrive(cleanerID: b, jobID: j.id, at: T("08:00"))
        try f.store.depart(cleanerID: b, jobID: j.id, at: T("11:30"))
        #expect(f.store.invoice(forJob: j.id) == nil)
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("12:00"))
        let x = f.job(j.id), inv = try #require(f.store.invoice(forJob: j.id))
        #expect(same(x.state, "complete") && same(x.invoiceID, inv.id))
        #expect(same(inv.jobID, j.id) && same(inv.issuedAt, T("12:00")) && !inv.settled)
        let lines = inv.lines.sorted { $0.cleanerID < $1.cleanerID }.map { "\($0.cleanerID) \($0.workedMinutes) \($0.amount)" }
        #expect(same(lines, ["\(a) 240 \(Decimal(string: "180.00")!)", "\(b) 210 \(Decimal(string: "157.50")!)"]))
        #expect(same(inv.total, Decimal(string: "337.50")!))
    }

    @Test func equalTapsMakeAZeroLine() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let j = try f.book(try f.client(), 1, 1, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("08:00"))
        let inv = try #require(f.store.invoice(forJob: j.id))
        #expect(same(inv.lines.map(\.amount), [Decimal(0)]) && same(inv.total, Decimal(0)))
    }

    @Test func settlement() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let j = try f.book(try f.client(), 1, 4, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("11:23"))  // 203 min: $152.25
        let inv = try #require(f.store.invoice(forJob: j.id))
        #expect(same(inv.total, Decimal(string: "152.25")!))
        f.fails(["paymentAmountMismatch"]) { try f.store.recordPayment(invoiceID: inv.id, amount: Decimal(100), at: T("13:00")) }
        f.fails(["paymentAmountMismatch"]) { try f.store.recordPayment(invoiceID: inv.id, amount: Decimal(string: "152.26")!, at: T("13:00")) }
        f.fails(["notFound"]) { try f.store.recordPayment(invoiceID: 9999, amount: Decimal(1), at: T("13:00")) }
        try f.store.recordPayment(invoiceID: inv.id, amount: Decimal(string: "152.25")!, at: T("13:00"))
        let paid = try #require(f.store.invoice(forJob: j.id))
        #expect(paid.settled && same(paid.paymentAmount, Decimal(string: "152.25")!) && same(paid.paymentDate, T("13:00")))
        f.fails(["alreadySettled"]) { try f.store.recordPayment(invoiceID: inv.id, amount: Decimal(string: "152.25")!, at: T("13:05")) }
    }

    @Test func invoicesSurviveASave() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let j = try f.book(try f.client(), 1, 1, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("09:00"))
        let before = f.snapshot()
        try f.store.save()
        try f.reopen()
        #expect(same(f.snapshot(), before) && f.store.invoice(forJob: j.id) != nil)
    }
}
