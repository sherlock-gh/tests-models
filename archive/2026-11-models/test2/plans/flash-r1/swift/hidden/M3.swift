// Milestone 3 (Flash-Next's plan): extensions and their rebooking, removals (US4), and utilization (US5):
// worked time on the day of departure, against 8 h a day and 40 h a Monday-to-Sunday week (research D-8).
import Foundation
import Testing
import CleaningLogic

@Suite struct M3ExtensionsRemovalsUtilization {
    @Test func extensionMovesTheNextJob() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let cl = try f.client()
        let j1 = try f.book(cl, 1, 4, MON), j2 = try f.book(cl, 1, 4, MON)   // 8:00-12:00, 13:00-17:00
        try f.store.arrive(cleanerID: a, jobID: j1.id, at: T("08:00"))
        try f.store.extend(cleanerID: a, jobID: j1.id)
        #expect(same(f.job(j1.id).bookedEnd, T("12:20")))
        let k = f.job(j2.id)                                            // 13:20 + 4 h passes 17:00: Tuesday
        #expect(same(slot(k), slot(TUE, 480)) && same(cleanersOf(k), [a]) && same(k.state, "scheduled"))
    }

    @Test func movedJobStartsAnHourAfterTheNewEnd() throws {
        let f = try Fixture()
        let a = try f.cleaners(2)[0]
        let cl = try f.client()
        let first = try f.book(cl, 1, 4, MON), other = try f.book(cl, 1, 4, MON), j2 = try f.book(cl, 1, 2, MON)
        #expect(same(cleanersOf(first), [a]) && same(cleanersOf(j2), [a]) && same(slot(j2), slot(MON, 780)))
        try f.store.arrive(cleanerID: a, jobID: first.id, at: T("08:00"))
        try f.store.extend(cleanerID: a, jobID: first.id)
        try f.store.extend(cleanerID: a, jobID: first.id)               // a now ends 12:40
        #expect(same(slot(f.job(j2.id)), slot(MON, 820)) && same(slot(f.job(other.id)), slot(MON, 480)))
    }

    @Test func moreThanAnHourLeftMovesNothing() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2), a = ids[0]
        let cl = try f.client()
        let x = try f.book(cl, 1, 4, MON)                               // a 8:00-12:00
        _ = try f.book(cl, 1, 4.5, MON)                                 // b 8:00-12:30
        let z = try f.book(cl, 2, 2, MON)                               // a and b 13:30-15:30
        #expect(same(cleanersOf(x), [a]) && same(slot(z), slot(MON, 810)) && same(cleanersOf(z), ids))
        try f.store.arrive(cleanerID: a, jobID: x.id, at: T("08:00"))
        try f.store.extend(cleanerID: a, jobID: x.id)                   // a ends 12:20: 70 minutes before 13:30
        #expect(same(slot(f.job(z.id)), slot(MON, 810)))
        try f.store.extend(cleanerID: a, jobID: x.id)                   // a ends 12:40: z must start 13:40 or later
        #expect(same(slot(f.job(z.id)), slot(MON, 820)) && same(cleanersOf(f.job(z.id)), ids))
    }

    @Test func extensionsMayPassFive() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let j = try f.book(try f.client(), 1, 9, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00"))
        try f.store.extend(cleanerID: a, jobID: j.id)
        try f.store.extend(cleanerID: a, jobID: j.id)
        #expect(same(f.job(j.id).bookedEnd, T("17:40")))
    }

    @Test func cleanerRemovalRebooksFutureJobs() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2)
        let j = try f.book(try f.client(), 1, 4, MON)
        #expect(same(cleanersOf(j), [ids[0]]))
        try f.store.deleteCleaner(id: ids[0])
        let k = f.job(j.id)
        #expect(same(slot(k), slot(MON, 480)) && same(cleanersOf(k), [ids[1]]) && same(k.state, "scheduled"))
    }

    @Test func cleanerRemovalRefusedWhenAJobWouldBeStranded() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        _ = try f.book(try f.client(), 1, 4, MON)
        f.fails(["notEnoughCleaners"]) { try f.store.deleteCleaner(id: a) }
    }

    @Test func clientRemovalCancelsFutureJobsAndKeepsInvoices() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let keep = try f.client("Keep"), gone = try f.client("Gone")
        let done = try f.book(gone, 1, 1, MON), later = try f.book(gone, 1, 2, TUE)
        try f.store.arrive(cleanerID: a, jobID: done.id, at: T("08:00"))
        try f.store.depart(cleanerID: a, jobID: done.id, at: T("09:00"))
        let inv = describe(try #require(f.store.invoice(forJob: done.id)))
        try f.store.deleteClient(id: gone)
        #expect(same(f.job(later.id).state, "cancelled") && same(f.job(done.id).state, "complete"))
        #expect(same(f.store.invoice(forJob: done.id).map(describe), inv))
        #expect(same(slot(try f.book(keep, 1, 2, TUE)), slot(TUE, 480)))   // a cancelled job blocks no one
    }

    @Test func utilizationDayAndWeek() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2), (a, b) = (ids[0], ids[1])
        let cl = try f.client()
        for day in ["2027-11-15", "2027-11-16", "2027-11-17", "2027-11-18", "2027-11-19"] {   // a: 6 h each weekday
            let j = try f.book(cl, 1, 6, day)
            try f.store.arrive(cleanerID: a, jobID: j.id, at: T("08:00", day))
            try f.store.depart(cleanerID: a, jobID: j.id, at: T("14:00", day))
        }
        let n = try f.book(cl, 1, 1, NEXT_MON)                          // next week: not counted
        try f.store.arrive(cleanerID: a, jobID: n.id, at: T("08:00", NEXT_MON))
        try f.store.depart(cleanerID: a, jobID: n.id, at: T("09:00", NEXT_MON))
        let rows = Dictionary(uniqueKeysWithValues: f.store.utilizationReports(day: TestTime.day(TUE)).map { ($0.cleanerID, $0) })
        #expect(same(Set(rows.keys), Set([a, b])))
        #expect(same(rows[a]!.dayWorkedMinutes, 360) && same(rows[a]!.weekWorkedMinutes, 1800))
        #expect(same(rows[b]!.dayWorkedMinutes, 0) && same(rows[b]!.weekWorkedMinutes, 0))
    }

    @Test func workCountsOnTheDayOfDeparture() throws {
        let f = try Fixture()
        let a = try f.cleaners(1)[0]
        let j = try f.book(try f.client(), 1, 1, MON)
        try f.store.arrive(cleanerID: a, jobID: j.id, at: T("23:00", MON))
        try f.store.depart(cleanerID: a, jobID: j.id, at: T("01:00", TUE))
        let mon = f.store.utilizationReports(day: TestTime.day(MON)), tue = f.store.utilizationReports(day: TestTime.day(TUE))
        #expect(same(mon.map(\.dayWorkedMinutes), [0]) && same(tue.map(\.dayWorkedMinutes), [120]) && same(tue.map(\.weekWorkedMinutes), [120]))
    }
}
