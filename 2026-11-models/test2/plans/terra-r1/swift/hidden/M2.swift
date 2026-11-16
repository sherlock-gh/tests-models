// Milestone 2 (Terra's plan): the cleaner's day, arrival and departure, extensions and their
// rebooking (US2), and invoices and payment (US3)
import Foundation
import Testing
import CleaningLogic

@Suite(.serialized) final class M2WorkBillingTests: Fixture {
    func arrive(_ j: Job, _ c: Int, _ hm: String, _ day: String = MON) throws -> Job { at(day, hm); return try svc.arrive(jobId: j.id, cleanerId: c) }
    func depart(_ j: Job, _ c: Int, _ hm: String, _ day: String = MON) throws -> Job { at(day, hm); return try svc.depart(jobId: j.id, cleanerId: c) }

    @Test func testAssignedJobs() throws {
        let ids = try cleaners(2)
        let cl = try client()
        let j1 = try book(cl, 1, 240, MON), j2 = try book(cl, 1, 240, MON), j3 = try book(cl, 1, 120, MON)
        _ = try book(cl, 1, 60, TUE)
        #expect(same(try svc.assignedJobs(cleanerId: ids[0], date: MON).map { $0.id }, [j1.id, j3.id]))
        #expect(same(try svc.assignedJobs(cleanerId: ids[1], date: MON).map { $0.id }, [j2.id]))
        fails(["not_found"]) { try svc.assignedJobs(cleanerId: 9999, date: MON) }
    }

    @Test func testArriveAndDepartUseTheClock() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 2, 240, MON)
        var x = try arrive(j, ids[0], "08:02")
        #expect(same(x.status, "in_progress"))
        #expect(same(x.work.first { $0.cleanerId == ids[0] }?.arrivedAt, "\(MON)T08:02:00"))
        #expect((x.work.first { $0.cleanerId == ids[1] }?.arrivedAt) == nil)
        x = try depart(j, ids[0], "10:02")
        #expect(same(x.work.first { $0.cleanerId == ids[0] }?.elapsedSeconds, 7200))
        #expect(same(x.status, "in_progress"))
    }

    @Test func testBadSequencesChangeNothing() throws {
        let ids = try cleaners(2)
        let spare = try svc.createCleaner(name: "Spare").id
        let j = try book(try client(), 2, 240, MON)
        at(MON, "09:00")
        fails { try svc.depart(jobId: j.id, cleanerId: ids[0]) }
        fails { try svc.arrive(jobId: j.id, cleanerId: spare) }
        fails(["not_found"]) { try svc.arrive(jobId: 9999, cleanerId: ids[0]) }
        _ = try arrive(j, ids[0], "08:00")
        at(MON, "08:05")
        fails { try svc.arrive(jobId: j.id, cleanerId: ids[0]) }
        at(MON, "07:59")
        fails { try svc.depart(jobId: j.id, cleanerId: ids[0]) }
    }

    @Test func testExtensionMovesTheNextJob() throws {
        let a = try cleaners(1)[0]
        let cl = try client()
        let j1 = try book(cl, 1, 240, MON), j2 = try book(cl, 1, 240, MON)
        _ = try arrive(j1, a, "08:00")
        #expect(same(try svc.extend(jobId: j1.id, cleanerId: a, increments: 1).endMinute, 740))
        let k = try svc.getJob(id: j2.id)
        #expect(same([k.date, "\(k.startMinute)", "\(k.endMinute)", "\(k.cleanerIds)"], [TUE, "480", "720", "\([a])"]))
    }

    @Test func testAFullHourLeftMovesNothing() throws {
        let ids = try cleaners(2)
        let cl = try client()
        let x = try book(cl, 1, 240, MON)
        _ = try book(cl, 1, 260, MON)
        let z = try book(cl, 2, 120, MON)
        #expect(same(z.startMinute, 800))
        _ = try arrive(x, ids[0], "08:00")
        _ = try svc.extend(jobId: x.id, cleanerId: ids[0], increments: 1)
        #expect(same(try svc.getJob(id: z.id).startMinute, 800))
        _ = try svc.extend(jobId: x.id, cleanerId: ids[0], increments: 1)
        let k = try svc.getJob(id: z.id)
        #expect(same([k.date, "\(k.startMinute)", "\(k.cleanerIds)"], [MON, "820", "\(ids)"]))
    }

    @Test func testIncrementsAndLateEnds() throws {
        let a = try cleaners(1)[0]
        let j = try book(try client(), 1, 540, MON)
        fails(["invalid_state", "invalid_input"]) { try svc.extend(jobId: j.id, cleanerId: a, increments: 1) }   // not started
        _ = try arrive(j, a, "08:00")
        for n in [0, -1] { fails(["invalid_input"]) { try svc.extend(jobId: j.id, cleanerId: a, increments: n) } }
        #expect(same(try svc.extend(jobId: j.id, cleanerId: a, increments: 2).endMinute, 1060))
        #expect(same(try svc.extend(jobId: j.id, cleanerId: a, increments: 3).endMinute, 1120))
        _ = try depart(j, a, "18:40")
        fails(["invalid_state", "invalid_input"]) { try svc.extend(jobId: j.id, cleanerId: a, increments: 1) }
    }

    @Test func testInvoiceOnLastDeparture() throws {
        let ids = try cleaners(2)
        let j = try book(try client("Home 7"), 2, 240, MON)
        _ = try arrive(j, ids[0], "08:00"); _ = try arrive(j, ids[1], "08:00")
        _ = try depart(j, ids[0], "12:00")
        #expect(same(svc.listInvoices(settled: nil), []))
        #expect(same(try depart(j, ids[1], "12:10").status, "completed"))
        let inv = svc.listInvoices(settled: nil)[0]
        #expect(same([inv.jobId, inv.totalCents], [j.id, 36750]))
        #expect(same([inv.clientName, inv.issuedAt], ["Home 7", "\(MON)T12:10:00"]))
        #expect(same(inv.lines.sorted { $0.cleanerId < $1.cleanerId }.map { [$0.cleanerId, $0.elapsedSeconds] }, [[ids[0], 14400], [ids[1], 15000]]))
    }

    @Test func testTotalRoundedOnce() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 2, 60, MON)
        _ = try arrive(j, ids[0], "08:00"); _ = try arrive(j, ids[1], "08:00")
        now = "\(MON)T08:00:01"
        _ = try svc.depart(jobId: j.id, cleanerId: ids[0]); _ = try svc.depart(jobId: j.id, cleanerId: ids[1])
        #expect(same(svc.listInvoices(settled: nil)[0].totalCents, 3))   // 2 s at 1.25 c/s, rounded once, half up
    }

    @Test func testPayInFullOnly() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 2, 240, MON)
        _ = try arrive(j, ids[0], "08:00"); _ = try arrive(j, ids[1], "08:00")
        _ = try depart(j, ids[0], "12:00"); _ = try depart(j, ids[1], "12:10")
        let inv = svc.listInvoices(settled: nil)[0]
        fails(["payment_mismatch"]) { try svc.payInvoice(id: inv.id, amountCents: 30000) }
        #expect(same(svc.listInvoices(settled: false), [inv]))
        #expect(try svc.payInvoice(id: inv.id, amountCents: 36750).settled)
        fails(["invalid_state", "payment_mismatch"]) { try svc.payInvoice(id: inv.id, amountCents: 36750) }
        #expect(same(svc.listInvoices(settled: true).map { $0.id }, [inv.id]))
        svc = try service()
        #expect(same(svc.listInvoices(settled: true).map { $0.id }, [inv.id]))
    }
}
