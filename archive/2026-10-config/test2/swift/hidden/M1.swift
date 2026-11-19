// Hidden acceptance tests for milestone 1 (test 2), from October's HabitKit tests; run with every
// earlier milestone's file. Calendar: Gregorian, UTC, weeks starting on Monday. 2026-03-02 is a Monday.
import Foundation
import Testing
import HabitKit

let utc: Calendar = {
    var c = Calendar(identifier: .gregorian)
    c.timeZone = TimeZone(identifier: "UTC")!
    c.firstWeekday = 2
    return c
}()

func d(_ s: String) -> Day {
    let p = s.split(separator: "-").map { Int($0)! }
    return Day(year: p[0], month: p[1], day: p[2])!
}

// 1. Day
@Test func dayRejectsImpossibleDates() {
    #expect(Day(year: 2026, month: 2, day: 29) == nil)
    #expect(Day(year: 2024, month: 2, day: 29) != nil)
    #expect(Day(year: 2026, month: 13, day: 1) == nil)
}

@Test func dayFromDateUsesCalendarTimeZone() {
    var la = Calendar(identifier: .gregorian)
    la.timeZone = TimeZone(identifier: "America/Los_Angeles")!
    let instant = ISO8601DateFormatter().date(from: "2026-03-01T03:00:00Z")!
    #expect(Day(instant, in: la) == d("2026-02-28"))
    #expect(Day(instant, in: utc) == d("2026-03-01"))
}

@Test func dayAddingCrossesMonthsAndYears() {
    #expect(d("2025-12-31").adding(days: 1) == d("2026-01-01"))
    #expect(d("2026-03-01").adding(days: -1) == d("2026-02-28"))
    #expect(d("2026-01-30").adding(days: 30) == d("2026-03-01"))
}

@Test func daysCompareInDateOrder() {
    #expect(d("2025-12-31") < d("2026-01-01"))
    #expect(d("2026-02-28") < d("2026-03-01"))
    #expect([d("2026-03-05"), d("2026-01-09"), d("2026-02-01")].sorted() == [d("2026-01-09"), d("2026-02-01"), d("2026-03-05")])
}
