// Milestone 2: the cleaner's day, Arrive and Depart, invoices and payment (plan US3, US4; C8-C12, C17)
import Foundation
import Testing
import CleaningCore

@Suite(.serialized) final class M2FieldBillingTests: Fixture {
    func ts(_ day: String, _ hm: String) -> String { "\(day)T\(hm):00" }

    func twoCleanerJob() throws -> (Int, Int, Int, Job) {
        let ids = try cleaners(2)
        let cl = try client("Home 7")
        return (ids[0], ids[1], cl, try book(cl, 2, 240, MON))
    }

    @Test func testCleanerDayView() throws {
        let ids = try cleaners(2)
        let cl = try client()
        let j1 = try book(cl, 1, 240, MON), j2 = try book(cl, 1, 240, MON), j3 = try book(cl, 1, 120, MON)
        _ = try book(cl, 1, 60, TUE)
        #expect(same(try svc.cleanerDay(cleanerId: ids[0], date: MON).map { $0.id }, [j1.id, j3.id]))
        #expect(same(try svc.cleanerDay(cleanerId: ids[1], date: MON).map { $0.id }, [j2.id]))
        fails(["not_found"]) { try svc.cleanerDay(cleanerId: 9999, date: MON) }
    }

    @Test func testArriveAndDepart() throws {
        let (a, b, _, j) = try twoCleanerJob()
        var x = try svc.arrive(jobId: j.id, cleanerId: a, timestamp: ts(MON, "08:02"))
        #expect(same(x.status, "in_progress"))
        #expect(same(x.timeEntries.first { $0.cleanerId == a }?.arrivedAt, ts(MON, "08:02")))
        #expect((x.timeEntries.first { $0.cleanerId == b }?.arrivedAt) == nil)
        x = try svc.depart(jobId: j.id, cleanerId: a, timestamp: ts(MON, "10:02"))
        #expect(same(x.timeEntries.first { $0.cleanerId == a }?.secondsWorked, 7200))
        #expect(same(x.status, "in_progress"))
    }

    @Test func testC9BadSequencesChangeNothing() throws {
        let (a, _, _, j) = try twoCleanerJob()
        let c = try svc.createCleaner(name: "Spare").id
        fails(["invalid_state"]) { try svc.depart(jobId: j.id, cleanerId: a, timestamp: ts(MON, "09:00")) }
        fails { try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00")) }
        fails(["invalid_input"]) { try svc.arrive(jobId: j.id, cleanerId: a, timestamp: "8 o'clock") }
        fails(["not_found"]) { try svc.arrive(jobId: 9999, cleanerId: a, timestamp: ts(MON, "08:00")) }
        _ = try svc.arrive(jobId: j.id, cleanerId: a, timestamp: ts(MON, "08:00"))
        fails(["invalid_state"]) { try svc.arrive(jobId: j.id, cleanerId: a, timestamp: ts(MON, "08:05")) }
        fails { try svc.depart(jobId: j.id, cleanerId: a, timestamp: ts(MON, "07:59")) }
    }

    @Test func testC10C11InvoiceOnLastDeparture() throws {
        let (a, b, _, j) = try twoCleanerJob()
        for c in [a, b] { _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00")) }
        _ = try svc.depart(jobId: j.id, cleanerId: a, timestamp: ts(MON, "12:00"))
        #expect(same(svc.listInvoices(settled: nil), []))
        #expect(same(try svc.depart(jobId: j.id, cleanerId: b, timestamp: ts(MON, "12:10")).status, "complete"))
        let invs = svc.listInvoices(settled: nil)
        #expect(same(invs.count, 1))
        let inv = invs[0]
        #expect(same([inv.jobId, inv.totalCents], [j.id, 36750]))
        #expect(same(inv.clientName, "Home 7"))
        #expect(!(inv.settled))
        let lines = inv.lines.sorted { $0.cleanerId < $1.cleanerId }
        #expect(same(lines.map { [$0.cleanerId, $0.secondsWorked, $0.chargeCents] }, [[a, 14400, 18000], [b, 15000, 18750]]))
        #expect(same(Set(lines.map { $0.cleanerName }), ["Cleaner 0", "Cleaner 1"]))
        #expect(same(try svc.getInvoice(id: inv.id), inv))
    }

    @Test func testC17RoundingToTheNearestCent() throws {
        for (secs, cents) in [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5), (4980, 6225)] {
            let c = try svc.createCleaner(name: "C\(secs)").id
            let j = try book(try client(), 1, 60, MON)
            #expect(same(j.cleanerIds, [c]))
            _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00"))
            let h = secs / 3600, m = secs % 3600 / 60, s = secs % 60
            _ = try svc.depart(jobId: j.id, cleanerId: c, timestamp: String(format: "%@T%02d:%02d:%02d", MON, 8 + h, m, s))
            let inv = svc.listInvoices(settled: nil).last!
            #expect(same([inv.lines[0].chargeCents, inv.totalCents], [cents, cents]), Comment(rawValue: "\(secs) s"))
        }
    }

    @Test func testC12PayInFullOnly() throws {
        let (a, b, _, j) = try twoCleanerJob()
        for c in [a, b] { _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00")) }
        _ = try svc.depart(jobId: j.id, cleanerId: a, timestamp: ts(MON, "12:00"))
        _ = try svc.depart(jobId: j.id, cleanerId: b, timestamp: ts(MON, "12:10"))
        let inv = svc.listInvoices(settled: nil)[0]
        fails(["payment_mismatch"]) { try svc.payInvoice(id: inv.id, amountCents: 30000) }
        fails(["payment_mismatch"]) { try svc.payInvoice(id: inv.id, amountCents: 36751) }
        #expect(same(svc.listInvoices(settled: false), [inv]))
        #expect(try svc.payInvoice(id: inv.id, amountCents: 36750).settled)
        fails(["invalid_state"]) { try svc.payInvoice(id: inv.id, amountCents: 36750) }
        #expect(same(svc.listInvoices(settled: false), []))
        #expect(same(svc.listInvoices(settled: true).map { $0.id }, [inv.id]))
        fails(["not_found"]) { try svc.payInvoice(id: 9999, amountCents: 1) }
    }

    @Test func testC8InvoicesKeepTheirNames() throws {
        let (a, b, cl, j) = try twoCleanerJob()
        let later = try book(cl, 1, 120, TUE)
        for c in [a, b] {
            _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00"))
            _ = try svc.depart(jobId: j.id, cleanerId: c, timestamp: ts(MON, "11:00"))
        }
        let invs = svc.listInvoices(settled: nil)
        _ = try svc.updateCleaner(id: a, name: "Renamed")
        try svc.deleteClient(id: cl)
        #expect(same(svc.listInvoices(settled: nil), invs))
        #expect(same(try svc.getJob(id: later.id).status, "cancelled"))
        #expect(same(try svc.getJob(id: j.id).status, "complete"))
    }

    @Test func testCompletedAndCancelledJobsTakeNoTaps() throws {
        let (a, b, cl, j) = try twoCleanerJob()
        for c in [a, b] {
            _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00"))
            _ = try svc.depart(jobId: j.id, cleanerId: c, timestamp: ts(MON, "09:00"))
        }
        fails { try svc.arrive(jobId: j.id, cleanerId: a, timestamp: ts(MON, "10:00")) }
        let k = try book(cl, 1, 60, TUE)
        try svc.deleteClient(id: cl)
        fails { try svc.arrive(jobId: k.id, cleanerId: k.cleanerIds[0], timestamp: ts(TUE, "08:00")) }
        #expect(same(svc.listInvoices(settled: nil).count, 1))
    }

    @Test func testInvoicesSurviveANewService() throws {
        let (a, b, _, j) = try twoCleanerJob()
        for c in [a, b] {
            _ = try svc.arrive(jobId: j.id, cleanerId: c, timestamp: ts(MON, "08:00"))
            _ = try svc.depart(jobId: j.id, cleanerId: c, timestamp: ts(MON, "09:00"))
        }
        let invs = svc.listInvoices(settled: nil)
        svc = try CleaningService(storeURL: url)
        #expect(same(svc.listInvoices(settled: nil), invs))
    }
}
