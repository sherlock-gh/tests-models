// Hidden acceptance tests for milestone 4 (test 2), from October's HabitKit tests; run with every
// earlier milestone's file. Calendar: Gregorian, UTC, weeks starting on Monday. 2026-03-02 is a Monday.
import Foundation
import Testing
import HabitKit

// 4. Streaks
@Test func dailyStreakEndsToday() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    try checkIns(s, h.id, ["2026-03-03", "2026-03-04", "2026-03-05"], today: "2026-03-05")
    #expect(s.currentStreak(for: h.id, today: d("2026-03-05")) == 3)
}

@Test func dailyStreakLeavesTodayOpenAndBreaksOnGaps() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    try checkIns(s, h.id, ["2026-03-01", "2026-03-03", "2026-03-04"], today: "2026-03-05")
    #expect(s.currentStreak(for: h.id, today: d("2026-03-05")) == 2)
    #expect(s.currentStreak(for: h.id, today: d("2026-03-06")) == 0)
}

@Test func streakIgnoresDaysBeforeCreation() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-05"))
    try checkIns(s, h.id, ["2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"], today: "2026-03-06")
    #expect(s.currentStreak(for: h.id, today: d("2026-03-06")) == 2)
}

@Test func weekdayStreakSkipsUnscheduledDays() throws {
    let (s, _) = try store()   // Monday, Wednesday, Friday
    let h = try s.addHabit(name: "Gym", schedule: .weekdays([2, 4, 6]), on: d("2026-03-02"))
    try checkIns(s, h.id, ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-06", "2026-03-09"], today: "2026-03-10")
    #expect(s.currentStreak(for: h.id, today: d("2026-03-10")) == 4)   // Tuesday: unscheduled
    #expect(s.currentStreak(for: h.id, today: d("2026-03-11")) == 4)   // Wednesday, still open
    #expect(s.currentStreak(for: h.id, today: d("2026-03-12")) == 0)   // Wednesday missed
}

@Test func weekdayStreakBreaksOnAMissedScheduledDay() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Gym", schedule: .weekdays([2, 4, 6]), on: d("2026-03-02"))
    try checkIns(s, h.id, ["2026-03-02", "2026-03-06", "2026-03-09"], today: "2026-03-10")
    #expect(s.currentStreak(for: h.id, today: d("2026-03-10")) == 2)
}

@Test func weeklyStreakCountsCompleteWeeks() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Swim", schedule: .timesPerWeek(2), on: d("2026-03-02"))
    try checkIns(s, h.id, ["2026-03-02", "2026-03-05",                  // week of 2 Mar: 2
                           "2026-03-09", "2026-03-10", "2026-03-15",    // week of 9 Mar: 3
                           "2026-03-17"], today: "2026-03-18")          // week of 16 Mar: 1 so far
    #expect(s.currentStreak(for: h.id, today: d("2026-03-18")) == 2)
    try s.checkIn(h.id, on: d("2026-03-18"), today: d("2026-03-18"))
    #expect(s.currentStreak(for: h.id, today: d("2026-03-18")) == 3)
}
