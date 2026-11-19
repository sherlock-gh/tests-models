// Milestone 4 (Flash-Next's iteration 3 plan): utilization (US6).
import Foundation
import Testing
import CleaningKit

func dailyHours(_ f: Fixture, _ day: String) -> [String] {
    f.store.dailyUtilization(date: TT.day(day)).map { "\($0.cleanerId) \($0.hoursWorked) \($0.hoursOf)" }.sorted()
}

func weeklyHours(_ f: Fixture, _ monday: String) -> [String] {
    f.store.weeklyUtilization(weekOf: TT.day(monday)).map { "\($0.cleanerId) \($0.hoursWorked) \($0.hoursOf)" }.sorted()
}

func work(_ f: Fixture, _ job: Int, _ c: Int, _ d1: String, _ t1: String, _ d2: String, _ t2: String) throws {
    _ = try f.arrive(job, c, d1, t1)
    _ = try f.depart(job, c, d2, t2)
}

@Test func hoursOutOfEightAndForty() throws {
    // US6: 3 h 30 min on Monday is 3.5 of 8; a cleaner with no taps shows 0, not an error
    let f = try Fixture()
    let cs = try f.cleaners(2)
    let j = try f.book(try f.client(), 1, 240, MON)
    let c = j.cleanerIds[0], idle = cs.first { $0 != c }!
    try work(f, j.id, c, MON, "08:00", MON, "11:30")
    #expect(dailyHours(f, MON) == ["\(c) 3.5 8", "\(idle) 0.0 8"].sorted())
    #expect(dailyHours(f, TUE) == ["\(c) 0.0 8", "\(idle) 0.0 8"].sorted())
    #expect(weeklyHours(f, MON) == ["\(c) 3.5 40", "\(idle) 0.0 40"].sorted())
    #expect(f.store.dailyUtilization(date: TT.day(MON)).map { "\($0.cleanerId) \($0.name)" }.sorted() == ["\(cs[0]) Cleaner 0", "\(cs[1]) Cleaner 1"].sorted())
}

@Test func workPastMidnightCountsOnEachDay() throws {
    // G9: 22:00 to 2:00 is 2 h on each day
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 240, MON)
    try work(f, j.id, a, MON, "22:00", TUE, "02:00")
    #expect(dailyHours(f, MON) == ["\(a) 2.0 8"] && dailyHours(f, TUE) == ["\(a) 2.0 8"])
    #expect(weeklyHours(f, MON) == ["\(a) 4.0 40"])
}

@Test func hoursAreNotCapped() throws {
    // G10: 45 h in a Monday-to-Sunday week shows as 45 of 40; work the next Monday is not in it
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    for d in [MON, TUE, WED, THU, FRI] {
        let j = try f.book(cl, 1, 480, d)
        #expect(String(startOf(j).prefix(10)) == d)
        try work(f, j.id, a, d, "08:00", d, "17:00")
    }
    let next = try f.book(cl, 1, 60, NEXT_MON)
    try work(f, next.id, a, NEXT_MON, "08:00", NEXT_MON, "09:00")
    #expect(dailyHours(f, MON) == ["\(a) 9.0 8"])
    #expect(weeklyHours(f, MON) == ["\(a) 45.0 40"])
    #expect(weeklyHours(f, NEXT_MON) == ["\(a) 1.0 40"])
}
