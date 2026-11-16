// Milestone 3: extensions and the rebooking they cause, and utilization (plan US5, US6; C13-C16)
import Foundation
import Testing
import CleaningCore

@Suite(.serialized) final class M3ExtensionUtilizationTests: Fixture {
    @Test func testC13ExtensionMovesTheNextJob() throws {
        let a = try cleaners(1)[0]
        let cl = try client()
        let j1 = try book(cl, 1, 240, MON), j2 = try book(cl, 1, 240, MON)
        #expect(same(try svc.requestExtension(jobId: j1.id, cleanerId: a, minutes: 20).endMinute, 740))
        let k = try svc.getJob(id: j2.id)                  // 13:20 + 4 h passes 17:00: Tuesday
        #expect(same([k.date, "\(k.startMinute)", "\(k.endMinute)", "\(k.cleanerIds)"], [TUE, "480", "720", "\([a])"]))
    }

    @Test func testMovedJobStartsAnHourAfterTheNewEnd() throws {
        let ids = try cleaners(2)
        let cl = try client()
        let first = try book(cl, 1, 240, MON)              // a 8:00-12:00
        let j1 = try book(cl, 1, 240, MON)                 // b 8:00-12:00
        let j2 = try book(cl, 1, 120, MON)                 // a 13:00-15:00
        #expect(same([first.cleanerIds, j2.cleanerIds], [[ids[0]], [ids[0]]]))
        _ = try svc.requestExtension(jobId: first.id, cleanerId: ids[0], minutes: 40)
        let k = try svc.getJob(id: j2.id)
        #expect(same([k.date, "\(k.startMinute)"], [MON, "820"]))
        #expect(same(try svc.getJob(id: j1.id).startMinute, 480))
    }

    @Test func testAFullHourLeftMovesNothing() throws {
        let ids = try cleaners(2)
        let cl = try client()
        let x = try book(cl, 1, 240, MON)                  // a 8:00-12:00
        _ = try book(cl, 1, 260, MON)                      // b 8:00-12:20
        let z = try book(cl, 2, 120, MON)                  // a and b 13:20-15:20
        #expect(same([x.cleanerIds, z.cleanerIds], [[ids[0]], ids]))
        #expect(same(z.startMinute, 800))
        _ = try svc.requestExtension(jobId: x.id, cleanerId: ids[0], minutes: 20)
        #expect(same(try svc.getJob(id: z.id).startMinute, 800))
        _ = try svc.requestExtension(jobId: x.id, cleanerId: ids[0], minutes: 20)
        let k = try svc.getJob(id: z.id)
        #expect(same([k.date, "\(k.startMinute)", "\(k.cleanerIds)"], [MON, "820", "\(ids)"]))
    }

    @Test func testC14C15AmountsAndLateEnds() throws {
        let a = try cleaners(1)[0]
        let j = try book(try client(), 1, 540, MON)
        for m in [30, 0, -20, 15] { fails(["invalid_input"]) { try svc.requestExtension(jobId: j.id, cleanerId: a, minutes: m) } }
        #expect(same(try svc.requestExtension(jobId: j.id, cleanerId: a, minutes: 40).endMinute, 1060))
        #expect(same(try svc.requestExtension(jobId: j.id, cleanerId: a, minutes: 60).endMinute, 1120))
    }

    @Test func testExtensionRefusals() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 1, 120, MON)
        fails { try svc.requestExtension(jobId: j.id, cleanerId: ids[1], minutes: 20) }
        fails(["not_found"]) { try svc.requestExtension(jobId: 9999, cleanerId: ids[0], minutes: 20) }
        _ = try svc.arrive(jobId: j.id, cleanerId: ids[0], timestamp: "\(MON)T08:00:00")
        #expect(same(try svc.requestExtension(jobId: j.id, cleanerId: ids[0], minutes: 20).endMinute, 620))
        _ = try svc.depart(jobId: j.id, cleanerId: ids[0], timestamp: "\(MON)T10:20:00")
        fails(["invalid_state"]) { try svc.requestExtension(jobId: j.id, cleanerId: ids[0], minutes: 20) }
    }

    @Test func testRandomExtensionsNeverOverlap() throws {
        var seed: UInt64 = 1116
        func next(_ n: Int) -> Int { seed = seed &* 6364136223846793005 &+ 1442695040888963407; return Int((seed >> 33) % UInt64(n)) }
        _ = try cleaners(6)
        let cl = try client()
        var jobs = [Job]()
        for _ in 0..<40 { jobs.append(try book(cl, [1, 1, 2][next(3)], 30 + next(451), TestDates.string(next(5)))) }
        for _ in 0..<40 {
            let j = try svc.getJob(id: jobs[next(jobs.count)].id)
            _ = try svc.requestExtension(jobId: j.id, cleanerId: j.cleanerIds[next(j.cleanerIds.count)], minutes: 20 * (1 + next(4)))
            assertNoOverlaps()
        }
        #expect(same(svc.listJobs().count, 40))
    }

    @Test func testC16DayAndWeek() throws {
        let ids = try cleaners(2)
        let cl = try client()
        for n in 0..<5 {
            let day = TestDates.string(n)
            let j = try book(cl, 1, 360, day)
            #expect(same(j.cleanerIds, [ids[0]]))
            _ = try svc.arrive(jobId: j.id, cleanerId: ids[0], timestamp: "\(day)T08:00:00")
            _ = try svc.depart(jobId: j.id, cleanerId: ids[0], timestamp: "\(day)T14:00:00")
        }
        let nxt = try book(cl, 1, 60, NEXT_MON)
        _ = try svc.arrive(jobId: nxt.id, cleanerId: ids[0], timestamp: "\(NEXT_MON)T08:00:00")
        _ = try svc.depart(jobId: nxt.id, cleanerId: ids[0], timestamp: "\(NEXT_MON)T09:00:00")
        let u = try svc.utilization(cleanerId: ids[0], date: TUE)
        #expect(same([u.date], [TUE]))
        #expect(same([u.daySeconds, u.weekSeconds], [21600, 108000]))
        #expect(abs((u.dayPercent) - (75)) < 0.01)
        #expect(abs((u.weekPercent) - (75)) < 0.01)
        let v = try svc.utilization(cleanerId: ids[1], date: TUE)
        #expect(same([v.daySeconds, v.weekSeconds], [0, 0]))
        fails(["not_found"]) { try svc.utilization(cleanerId: 9999, date: TUE) }
    }

    @Test func testWorkCountsOnTheDayOfArrival() throws {
        let a = try cleaners(1)[0]
        let j = try book(try client(), 1, 60, MON)
        _ = try svc.arrive(jobId: j.id, cleanerId: a, timestamp: "\(MON)T23:00:00")
        _ = try svc.depart(jobId: j.id, cleanerId: a, timestamp: "\(TUE)T01:00:00")
        #expect(same(try svc.utilization(cleanerId: a, date: MON).daySeconds, 7200))
        let t = try svc.utilization(cleanerId: a, date: TUE)
        #expect(same([t.daySeconds, t.weekSeconds], [0, 7200]))
    }
}
