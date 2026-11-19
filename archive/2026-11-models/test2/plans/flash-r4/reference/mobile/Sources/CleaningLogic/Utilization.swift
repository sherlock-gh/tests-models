import Foundation

extension CleaningApp {
    public func utilization(cleanerId: Int, from: Day, to: Day) -> Utilization {
        guard dayDate(from) != nil, dayDate(to) != nil, from <= to else { return Utilization(days: [], weeks: []) }
        var totals: [String: Int] = [:], current = from
        while current <= to { totals[current] = 0; current = addDays(current, 1) }
        for j in state.jobs {
            for p in j.parts { for a in p.assignments where a.cleanerId == cleanerId {
                guard let start = a.arrive.flatMap(parse), let end = a.depart.flatMap(parse), end > start else { continue }
                var cursor = start
                while cursor < end {
                    let date = String(format(cursor).prefix(10))
                    guard let midnight = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: cursor)) else { break }
                    let next = min(end, midnight)
                    if totals[date] != nil { totals[date, default: 0] += Int(next.timeIntervalSince(cursor) / 60) }
                    cursor = next
                }
            } }
        }
        let days = totals.keys.sorted().map { UtilizationDay(cleanerId: cleanerId, date: $0, minutes: totals[$0]!, of: 480) }
        var weekTotals: [String: Int] = [:]
        for entry in days {
            let date = dayDate(entry.date)!
            let weekday = calendar.component(.weekday, from: date)
            let monday = addDays(entry.date, -((weekday + 5) % 7))
            weekTotals[monday, default: 0] += entry.minutes
        }
        let weeks = weekTotals.keys.sorted().map { UtilizationWeek(cleanerId: cleanerId, weekStart: $0, minutes: weekTotals[$0]!, of: 2400) }
        return Utilization(days: days, weeks: weeks)
    }
}
