// Hidden acceptance tests for milestone 3 (test 2), from October's HabitKit tests; run with every
// earlier milestone's file. Calendar: Gregorian, UTC, weeks starting on Monday. 2026-03-02 is a Monday.
import Foundation
import Testing
import HabitKit

func store(_ name: String = UUID().uuidString) throws -> (HabitStore, URL) {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("habitkit-\(name).json")
    try? FileManager.default.removeItem(at: url)
    return (try HabitStore(fileURL: url, calendar: utc), url)
}

func checkIns(_ s: HabitStore, _ id: UUID, _ days: [String], today: String) throws {
    for x in days { try s.checkIn(id, on: d(x), today: d(today)) }
}

// 2-3. Habits
@Test func addHabitTrimsName() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "  Read  ", schedule: .daily, on: d("2026-03-01"))
    #expect(h.name == "Read")
    #expect(h.createdOn == d("2026-03-01"))
    #expect(!h.archived)
    #expect(s.habits.map(\.id) == [h.id])
}

@Test func emptyNameIsRejected() throws {
    let (s, _) = try store()
    #expect(throws: HabitError.emptyName) { try s.addHabit(name: "   ", schedule: .daily, on: d("2026-03-01")) }
}

@Test func duplicateNameIsRejectedUntilArchived() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Read", schedule: .daily, on: d("2026-03-01"))
    #expect(throws: HabitError.duplicateName) { try s.addHabit(name: "read", schedule: .daily, on: d("2026-03-01")) }
    try s.archive(h.id)
    let again = try s.addHabit(name: "READ", schedule: .daily, on: d("2026-03-02"))
    #expect(again.id != h.id)
}

@Test(arguments: [Schedule.weekdays([]), .weekdays([0]), .weekdays([2, 8]), .timesPerWeek(0), .timesPerWeek(8)])
func invalidSchedulesAreRejected(_ schedule: Schedule) throws {
    let (s, _) = try store()
    #expect(throws: HabitError.invalidSchedule) { try s.addHabit(name: "X", schedule: schedule, on: d("2026-03-01")) }
}

@Test func habitsSortByNameWithArchivedLast() throws {
    let (s, _) = try store()
    let b = try s.addHabit(name: "b", schedule: .daily, on: d("2026-03-01"))
    let a = try s.addHabit(name: "A", schedule: .daily, on: d("2026-03-01"))
    let c = try s.addHabit(name: "c", schedule: .daily, on: d("2026-03-01"))
    #expect(s.habits.map(\.id) == [a.id, b.id, c.id])
    try s.archive(a.id)
    #expect(s.habits.map(\.id) == [b.id, c.id, a.id])
    #expect(s.habits.last?.archived == true)
}

@Test func futureCheckInIsRejected() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    #expect(throws: HabitError.futureCheckIn) { try s.checkIn(h.id, on: d("2026-03-06"), today: d("2026-03-05")) }
}

@Test func checkInsAreSortedUniqueAndUndoable() throws {
    let (s, _) = try store()
    let h = try s.addHabit(name: "Run", schedule: .daily, on: d("2026-03-01"))
    try checkIns(s, h.id, ["2026-03-04", "2026-03-02", "2026-03-04"], today: "2026-03-05")
    #expect(s.checkIns(for: h.id) == [d("2026-03-02"), d("2026-03-04")])
    try s.undoCheckIn(h.id, on: d("2026-03-04"))
    try s.undoCheckIn(h.id, on: d("2026-03-03"))
    #expect(s.checkIns(for: h.id) == [d("2026-03-02")])
}

@Test func storeSavesAndLoads() throws {
    let (s, url) = try store()
    let h = try s.addHabit(name: "Run", schedule: .weekdays([2, 4]), on: d("2026-03-01"))
    let g = try s.addHabit(name: "Read", schedule: .timesPerWeek(3), on: d("2026-03-02"))
    try s.archive(g.id)
    try checkIns(s, h.id, ["2026-03-02", "2026-03-04"], today: "2026-03-05")
    try s.save()
    let t = try HabitStore(fileURL: url, calendar: utc)
    #expect(t.habits == s.habits)
    #expect(t.checkIns(for: h.id) == [d("2026-03-02"), d("2026-03-04")])
}

@Test func missingFileIsAnEmptyStore() throws {
    let (s, _) = try store()
    #expect(s.habits.isEmpty)
}
