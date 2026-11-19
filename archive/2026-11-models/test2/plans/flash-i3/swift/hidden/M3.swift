// Milestone 3 (Flash-Next's iteration 3 plan): more time (US3) and records with safe deletions (US4).
import Foundation
import Testing
import CleaningKit

@Test func moreTimeNeedsAnOpenArrive() throws {
    // G13: before Arrive, after Depart
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 60, MON)
    _ = f.refused([j.id], "more time before Arrive") { _ = try f.store.requestMoreTime(jobId: j.id, cleanerId: a) }
    _ = try f.arrive(j.id, a, MON, "08:00")
    _ = try f.depart(j.id, a, MON, "09:00")
    _ = f.refused([j.id], "more time after Depart") { _ = try f.store.requestMoreTime(jobId: j.id, cleanerId: a) }
    _ = f.refused([j.id], "more time on an unknown job") { _ = try f.store.requestMoreTime(jobId: 9999, cleanerId: a) }
}

@Test func twentyMinutesAStepPastFive() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 240, MON)
    _ = try f.arrive(j.id, a, MON, "08:00")
    var x = try f.store.requestMoreTime(jobId: j.id, cleanerId: a)
    #expect(spans(x.job) == ["\(MON)T08:00-\(MON)T12:20"] && x.rebooked.isEmpty)
    _ = try f.depart(j.id, a, MON, "12:20")
    let late = try f.book(try f.client("B"), 1, 240, TUE)
    _ = try f.arrive(late.id, a, TUE, "08:00")
    for _ in 0..<3 { x = try f.store.requestMoreTime(jobId: late.id, cleanerId: a) }
    #expect(spans(x.job) == ["\(TUE)T08:00-\(TUE)T13:00"])
    for _ in 0..<12 { x = try f.store.requestMoreTime(jobId: late.id, cleanerId: a) }
    #expect(spans(x.job) == ["\(TUE)T08:00-\(TUE)T17:00"])
    x = try f.store.requestMoreTime(jobId: late.id, cleanerId: a)
    #expect(spans(x.job) == ["\(TUE)T08:00-\(TUE)T17:20"])
}

@Test func aJobInTheShadowIsBookedAgain() throws {
    // G14: an hour after 12:20 is 13:20, so the 13:00 job moves to the first quarter hour after
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    let j = try f.book(cl, 1, 240, MON), later = try f.book(cl, 1, 60, MON)
    #expect(startOf(later) == "\(MON)T13:00")
    _ = try f.arrive(j.id, a, MON, "08:00")
    let x = try f.store.requestMoreTime(jobId: j.id, cleanerId: a)
    #expect(spans(x.job) == ["\(MON)T08:00-\(MON)T12:20"])
    #expect(x.rebooked.map(\.jobId) == [later.id])
    let moved = try f.job(later.id)
    #expect(moved.status == .booked && spans(moved) == ["\(MON)T13:30-\(MON)T14:30"])
    #expect(x.rebooked.first.map { $0.parts.map { "\(TT.string($0.start))-\(TT.string($0.end))" } } == spans(moved))
    assertNoOverlaps(try f.jobs([j.id, later.id]))
}

@Test func aBumpLeavesNoOverlap() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    let j = try f.book(cl, 1, 240, MON), b = try f.book(cl, 1, 60, MON), c = try f.book(cl, 1, 60, MON)
    _ = try f.arrive(j.id, a, MON, "08:00")
    let x = try f.store.requestMoreTime(jobId: j.id, cleanerId: a)
    #expect(x.rebooked.map(\.jobId).contains(b.id))
    let floor = TT.at(MON, "13:20")
    for r in x.rebooked { #expect(try f.job(r.jobId).parts[0].start >= floor) }
    #expect(try f.jobs([b.id, c.id]).allSatisfy { $0.status == .booked })
    assertNoOverlaps(try f.jobs([j.id, b.id, c.id]))
}

@Test func deletingACleanerBooksTheirFutureJobsAgain() throws {
    // G15: two future jobs go to a free cleaner; the job already arrived on is not moved
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    let arrived = try f.book(cl, 1, 240, MON), f1 = try f.book(cl, 1, 240, TUE), f2 = try f.book(cl, 1, 120, WED)
    #expect(Set(arrived.cleanerIds + f1.cleanerIds + f2.cleanerIds) == [a])
    let b = try f.cleaners(1, first: 1)[0]
    _ = try f.arrive(arrived.id, a, MON, "08:00")
    try f.store.deleteCleaner(id: a)
    #expect(f.store.cleaners().map(\.id) == [b])
    for (old, day) in [(f1, TUE), (f2, WED)] {
        let g = try f.job(old.id)
        #expect(g.status == .booked && g.cleanerIds == [b])
        #expect(g.parts[0].start >= TT.at(day, "00:00"))
    }
    let still = try f.job(arrived.id)
    #expect(still.status == .inProgress && spans(still) == spans(arrived))
    assertNoOverlaps(try f.jobs([arrived.id, f1.id, f2.id]))
}

@Test func deletingAClientCancelsTheirFutureJobs() throws {
    // G16: cancelled jobs stay on file and free their cleaners
    let f = try Fixture()
    _ = try f.cleaners(1)
    let keep = try f.client("Keep"), gone = try f.client("Gone")
    let j1 = try f.book(gone, 1, 240, MON), j2 = try f.book(gone, 1, 60, TUE), k = try f.book(keep, 1, 60, MON)
    try f.store.deleteClient(id: gone)
    #expect(f.store.clients().map(\.id) == [keep])
    #expect(try f.jobs([j1.id, j2.id]).map(\.status) == [.cancelled, .cancelled])
    #expect(try f.job(k.id).status == .booked)
    #expect(startOf(try f.book(keep, 1, 60, MON)) == "\(MON)T08:00")
}

@Test func aJobWithAnIssuedInvoiceStays() throws {
    // G17, and deleting a job nobody has arrived on frees its slot
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    let done = try f.book(cl, 1, 60, MON)
    _ = try f.arrive(done.id, a, MON, "08:00")
    let inv = try #require(try f.depart(done.id, a, MON, "09:00").invoice)
    let m = f.refused([done.id], "deleting an invoiced job") { try f.store.deleteJob(id: done.id) }
    #expect(m.lowercased().contains("invoice"))
    #expect(try f.job(done.id).invoiceId == inv.id && f.store.invoices().count == 1)
    let j = try f.book(cl, 1, 60, TUE)
    try f.store.deleteJob(id: j.id)
    #expect((try? f.store.job(id: j.id)) == nil)
    #expect(startOf(try f.book(cl, 1, 60, TUE)) == "\(TUE)T08:00")
}

@Test func deletingRecordsWithNothingToMove() throws {
    let f = try Fixture()
    let cs = try f.cleaners(2), cl = try f.client(), other = try f.client("Other")
    let j = try f.book(cl, 1, 60, MON)
    let idle = cs.first { !j.cleanerIds.contains($0) }!
    try f.store.deleteCleaner(id: idle)
    try f.store.deleteClient(id: other)
    let again = try f.job(j.id)
    #expect(spans(again) == spans(j) && again.status == .booked)
}
