// Hidden acceptance tests for milestone 2 (test 2), from October's HabitKit tests; run with every
// earlier milestone's file. Calendar: Gregorian, UTC, weeks starting on Monday. 2026-03-02 is a Monday.
import Foundation
import Testing
import HabitKit

// 2. Habit and schedule
@Test func schedulesRoundTripThroughJSON() throws {
    for s in [Schedule.daily, .weekdays([2, 4]), .timesPerWeek(3)] {
        #expect(try JSONDecoder().decode(Schedule.self, from: JSONEncoder().encode(s)) == s)
    }
}

@Test func habitHasTheSpecifiedFields() {
    let _: KeyPath<Habit, UUID> = \Habit.id
    let _: KeyPath<Habit, String> = \Habit.name
    let _: KeyPath<Habit, Schedule> = \Habit.schedule
    let _: KeyPath<Habit, Day> = \Habit.createdOn
    let _: KeyPath<Habit, Bool> = \Habit.archived
    let errors: [HabitError] = [.emptyName, .duplicateName, .invalidSchedule, .unknownHabit, .futureCheckIn]
    #expect(Set(errors.map { "\($0)" }).count == 5)
}
