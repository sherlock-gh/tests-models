// Milestone 3 (Terra's plan): removals and utilization (US4)
import Foundation
import Testing
import CleaningLogic

@Suite(.serialized) final class M3RemovalsUtilizationTests: Fixture {
    func work(_ j: Job, _ c: Int, _ day: String, _ from: String, _ to: String, _ toDay: String? = nil) throws {
        at(day, from); _ = try svc.arrive(jobId: j.id, cleanerId: c)
        at(toDay ?? day, to); _ = try svc.depart(jobId: j.id, cleanerId: c)
    }

    @Test func testClientRemovalCancelsFutureJobsOnly() throws {
        let a = try cleaners(1)[0]
        let keep = try client("Keep"), gone = try client("Gone")
        let done = try book(gone, 1, 60, MON), later = try book(gone, 1, 120, MON)
        try work(done, a, MON, "08:00", "09:00")
        let invs = svc.listInvoices(settled: nil)
        at(MON, "09:30")
        try svc.deleteClient(id: gone)
        #expect(same(try svc.getJob(id: later.id).status, "cancelled"))
        #expect(same(try svc.getJob(id: done.id).status, "completed"))
        #expect(same(svc.listInvoices(settled: nil), invs))
        fails(["not_found"]) { try svc.getClient(id: gone) }
        #expect(same(try book(keep, 1, 120, MON).startMinute, 600))
    }

    @Test func testPastJobsAreNotFuture() throws {
        _ = try cleaners(1)
        let cl = try client()
        let past = try book(cl, 1, 60, MON)
        at(MON, "09:00")
        try svc.deleteClient(id: cl)
        #expect(same(try svc.getJob(id: past.id).status, "scheduled"))
    }

    @Test func testCleanerRemovalRebooksFutureJobs() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 1, 240, MON)
        #expect(same(j.cleanerIds, [ids[0]]))
        try svc.deleteCleaner(id: ids[0])
        let k = try svc.getJob(id: j.id)
        #expect(same([k.date, "\(k.startMinute)", "\(k.cleanerIds)", k.status], [MON, "480", "\([ids[1]])", "scheduled"]))
        fails(["not_found"]) { try svc.getCleaner(id: ids[0]) }
    }

    @Test func testCleanerRemovalRefusedWhenAJobCannotBeRebooked() throws {
        let ids = try cleaners(1)
        _ = try book(try client(), 1, 240, MON)
        fails(["unschedulable", "invalid_state"]) { try svc.deleteCleaner(id: ids[0]) }
    }

    @Test func testDayAndWeek() throws {
        let ids = try cleaners(2)
        let cl = try client()
        for n in 0..<5 {
            let day = TestDates.string(n)
            let j = try book(cl, 1, 360, day)
            #expect(same(j.cleanerIds, [ids[0]]))
            try work(j, ids[0], day, "08:00", "14:00")
        }
        try work(try book(cl, 1, 60, NEXT_MON), ids[0], NEXT_MON, "08:00", "09:00")
        let u = try svc.utilization(cleanerId: ids[0], date: TUE)
        #expect(same([u.cleanerId, u.daySeconds, u.weekSeconds], [ids[0], 21600, 108000]))
        #expect(same(u.date, TUE))
        let v = try svc.utilization(cleanerId: ids[1], date: TUE)
        #expect(same([v.daySeconds, v.weekSeconds], [0, 0]))
        fails(["not_found"]) { try svc.utilization(cleanerId: 9999, date: TUE) }
    }

    @Test func testOnlyCompletedWorkCountsSplitAtMidnight() throws {
        let ids = try cleaners(2)
        let cl = try client()
        try work(try book(cl, 1, 60, MON), ids[0], MON, "23:00", "01:30", TUE)
        let k = try book(cl, 2, 60, TUE)
        at(TUE, "10:00")
        _ = try svc.arrive(jobId: k.id, cleanerId: ids[0]); _ = try svc.arrive(jobId: k.id, cleanerId: ids[1])
        at(TUE, "11:00")
        _ = try svc.depart(jobId: k.id, cleanerId: ids[0])
        #expect(same(try svc.utilization(cleanerId: ids[0], date: MON).daySeconds, 3600))
        let t = try svc.utilization(cleanerId: ids[0], date: TUE)
        #expect(same([t.daySeconds, t.weekSeconds], [5400, 9000]))
    }
}
