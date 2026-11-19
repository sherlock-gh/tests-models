# HabitKit: specification

A Swift package with the logic of a habit-tracking app (the part under the screens): habits, their schedules, check-ins, streaks and completion rates, saved to a JSON file. No UI.

## Ground rules

- Swift 6, Swift Package Manager, Foundation only; nothing can be installed.
- `Package.swift` at the repository root: package and library product `HabitKit`, target `HabitKit`, test target `HabitKitTests` using Swift Testing (`import Testing`), and `platforms: [.macOS(.v14), .iOS(.v17)]`.
- `swift build` and `swift test` must pass.
- Everything below is `public` exactly as written, so other code can use it with `import HabitKit`.

## 1. Day

A calendar date without a time:

```swift
public struct Day: Codable, Hashable, Comparable, Sendable {
    public let year: Int
    public let month: Int
    public let day: Int
    public init?(year: Int, month: Int, day: Int)        // nil for a date that doesn't exist (e.g. 2026-02-29)
    public init(_ date: Date, in calendar: Calendar)    // the day that `date` falls on in calendar's time zone
    public func adding(days: Int) -> Day                // across months and years
}
```

`Day`s compare in date order. Gregorian dates.

## 2. Habit and schedule

```swift
public enum Schedule: Codable, Equatable, Sendable {
    case daily
    case weekdays(Set<Int>)     // Calendar weekday numbers: 1 = Sunday ... 7 = Saturday
    case timesPerWeek(Int)      // n check-ins in each week; weeks start on the calendar's firstWeekday
}

public struct Habit: Codable, Equatable, Identifiable, Sendable {
    public let id: UUID
    public var name: String
    public var schedule: Schedule
    public var createdOn: Day
    public var archived: Bool
}

public enum HabitError: Error, Equatable {
    case emptyName, duplicateName, invalidSchedule, unknownHabit, futureCheckIn
}
```

## 3. HabitStore

```swift
public final class HabitStore {
    public init(fileURL: URL, calendar: Calendar) throws   // loads the file; a missing file is an empty store
    public var habits: [Habit] { get }                     // by name, case-insensitive; archived habits last
    @discardableResult
    public func addHabit(name: String, schedule: Schedule, on day: Day) throws -> Habit
    public func archive(_ id: UUID) throws
    public func checkIn(_ id: UUID, on day: Day, today: Day) throws
    public func undoCheckIn(_ id: UUID, on day: Day) throws
    public func checkIns(for id: UUID) -> [Day]            // ascending, no duplicates
    public func currentStreak(for id: UUID, today: Day) -> Int
    public func completionRate(for id: UUID, from: Day, through: Day) -> Double
    public func save() throws
}
```

- `addHabit` trims the name's surrounding whitespace. Empty after trimming: `emptyName`. The same name (case-insensitive) as another habit that isn't archived: `duplicateName`. `weekdays` empty or with a number outside 1...7, or `timesPerWeek` outside 1...7: `invalidSchedule`.
- `archive`, `checkIn`, `undoCheckIn` on an unknown id: `unknownHabit`. A check-in on a day after `today`: `futureCheckIn`. Checking in twice on the same day records it once; undoing a day that has no check-in does nothing.
- `save` writes the whole store to `fileURL` as JSON, atomically. A new `HabitStore` on the same file then has the same habits (ids included) and check-ins.

## 4. Streaks

`currentStreak(for:today:)`, for a known habit (0 for an unknown one). Days before the habit's `createdOn` never count, and check-ins on days the schedule doesn't ask for are ignored.

- `daily`: the number of consecutive days with a check-in, ending today. If today has no check-in yet, the count ends yesterday instead (today is still open).
- `weekdays`: the same, counting only the scheduled days (the days between are skipped). If today is a scheduled day without a check-in, the count ends at the previous scheduled day.
- `timesPerWeek(n)`: counted in weeks. A week is complete with at least n check-ins in it. The number of consecutive complete weeks, ending with the current week if it is complete, otherwise ending with the week before.

## 5. Completion rate

`completionRate(for:from:through:)`, between 0 and 1; 0 when the range (from `from` or the habit's `createdOn`, whichever is later, through `through`) is empty or the habit is unknown.

- `daily` and `weekdays`: scheduled days in the range with a check-in, divided by the scheduled days in the range.
- `timesPerWeek(n)`: over the weeks that start inside the range, the sum of `min(check-ins that week, n)` divided by `n` times the number of those weeks.

## 6. Tests and documentation

Tests in `Tests/HabitKitTests` for every section, using a fixed Gregorian calendar and time zone (never the machine's). A `README.md` with an example of creating a store, adding a habit, checking in and reading the streak.
