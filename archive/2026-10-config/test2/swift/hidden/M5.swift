// Hidden acceptance tests for milestone 5 (test 2), from October's HabitKit tests; run with every
// earlier milestone's file. Calendar: Gregorian, UTC, weeks starting on Monday. 2026-03-02 is a Monday.
import Foundation
import Testing
import HabitKit

// 5. Completion rate
@Test func dailyCompletionRate() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    try checkIns(s, h.id, ["2026-03-01", "2026-03-02", "2026-03-05", "2026-03-08", "2026-03-10"], today: "2026-03-10")
    #expect(s.completionRate(for: h.id, from: d("2026-03-01"), through: d("2026-03-10")) == 0.5)
}

@Test func completionRateStartsAtCreation() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-06"))
    try checkIns(s, h.id, ["2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10"], today: "2026-03-10")
    #expect(s.completionRate(for: h.id, from: d("2026-03-01"), through: d("2026-03-10")) == 1.0)
    #expect(s.completionRate(for: h.id, from: d("2026-03-01"), through: d("2026-03-05")) == 0)
}

@Test func weekdayCompletionRate() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Gym", schedule: .weekdays([2, 4, 6]), on: d("2026-03-02"))
    try checkIns(s, h.id, ["2026-03-02", "2026-03-03", "2026-03-06"], today: "2026-03-08")
    #expect(abs(s.completionRate(for: h.id, from: d("2026-03-02"), through: d("2026-03-08")) - 2.0 / 3.0) < 1e-9)
}

@Test func weeklyCompletionRate() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Swim", schedule: .timesPerWeek(2), on: d("2026-03-02"))
    try checkIns(s, h.id, ["2026-03-02", "2026-03-05", "2026-03-06", "2026-03-11"], today: "2026-03-15")
    #expect(s.completionRate(for: h.id, from: d("2026-03-02"), through: d("2026-03-15")) == 0.75)
    try s.checkIn(h.id, on: d("2026-03-12"), today: d("2026-03-15"))
    #expect(s.completionRate(for: h.id, from: d("2026-03-02"), through: d("2026-03-15")) == 1.0)
}

@Test func emptyRangeRateIsZero() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    #expect(s.completionRate(for: h.id, from: d("2026-03-10"), through: d("2026-03-05")) == 0)
}

@Test func unknownHabitIsAnError() throws {
    let (s, _) = try store()
    let id = UUID()
    #expect(throws: HabitError.unknownHabit) { try s.archive(id) }
    #expect(throws: HabitError.unknownHabit) { try s.checkIn(id, on: d("2026-03-01"), today: d("2026-03-01")) }
    #expect(throws: HabitError.unknownHabit) { try s.undoCheckIn(id, on: d("2026-03-01")) }
    #expect(s.checkIns(for: id).isEmpty)
    #expect(s.currentStreak(for: id, today: d("2026-03-01")) == 0)
    #expect(s.completionRate(for: id, from: d("2026-03-01"), through: d("2026-03-05")) == 0)
}
