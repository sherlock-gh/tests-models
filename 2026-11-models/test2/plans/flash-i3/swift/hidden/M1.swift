// Milestone 1 (Flash-Next's iteration 3 plan): records and booking (US1), through CleaningStore
// (contracts/cleaner-api.md, exact-interfaces.md). Monday 2027-11-15 is the first test day; no clock
// change falls in the weeks used.
import Foundation
import Testing
import CleaningKit

let MON = "2027-11-15", TUE = "2027-11-16", WED = "2027-11-17", THU = "2027-11-18", FRI = "2027-11-19", SAT = "2027-11-20"
let NEXT_MON = "2027-11-22"
let NO_SLOT = "No slot for this job within 90 days of the requested day."
let ZONE = TimeZone(identifier: "America/Los_Angeles")!

enum TT {
    nonisolated(unsafe) static let fmt: DateFormatter = {
        let f = DateFormatter(); var c = Calendar(identifier: .gregorian); c.timeZone = ZONE
        f.calendar = c; f.timeZone = ZONE; f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd'T'HH:mm"; return f
    }()
    static func at(_ day: String, _ hm: String) -> Date { fmt.date(from: "\(day)T\(hm)")! }
    static func string(_ d: Date) -> String { fmt.string(from: d) }
    static func day(_ s: String) -> DateComponents {
        let p = s.split(separator: "-").map { Int($0)! }
        return DateComponents(year: p[0], month: p[1], day: p[2])
    }
    static func plus(_ s: String, days n: Int) -> String {
        var c = Calendar(identifier: .gregorian); c.timeZone = ZONE
        return String(string(c.date(byAdding: .day, value: n, to: at(s, "12:00"))!).prefix(10))
    }
}

func spans(_ j: Job) -> [String] { j.parts.map { "\(TT.string($0.start))-\(TT.string($0.end))" } }
func startOf(_ j: Job) -> String { TT.string(j.parts[0].start) }

func describe(_ j: Job) -> String {
    let t = j.taps.map { "\($0.cleanerId) \($0.kind.rawValue) \(TT.string($0.instant))" }
    return "\(j.id) \(j.clientId) \(j.cleanersNeeded) \(j.expectedLengthMinutes) \(j.requestedDay.year ?? 0)-\(j.requestedDay.month ?? 0)-\(j.requestedDay.day ?? 0) "
        + "\(j.cleanerIds) \(j.status.rawValue) \(spans(j)) \(j.invoiceId ?? -1) \(t)"
}

func describe(_ i: Invoice) -> String {
    "\(i.id) \(i.jobId) \(TT.string(i.issuedAt)) \(i.lines.map { "\($0.cleanerId) \($0.minutesWorked) \($0.cents)" }) \(i.totalCents) \(i.settled)"
}

/// Booked parts: weekdays, on the quarter hour from 8:00, ending by 17:00; for each cleaner, every
/// part starts at least an hour after the other's end (rules-core I1-I3).
func assertNoOverlaps(_ jobs: [Job]) {
    var c = Calendar(identifier: .gregorian); c.timeZone = ZONE
    var per = [Int: [(Date, Date, Int)]]()
    for j in jobs where j.status != .cancelled {
        for p in j.parts {
            if j.status == .booked {
                let w = c.component(.weekday, from: p.start), h = c.component(.hour, from: p.start), m = c.component(.minute, from: p.start)
                let five = c.date(bySettingHour: 17, minute: 0, second: 0, of: p.start)!
                #expect(w != 1 && w != 7 && h >= 8 && m % 15 == 0 && p.end <= five, "job \(j.id): \(spans(j))")
            }
            for k in j.cleanerIds { per[k, default: []].append((p.start, p.end, j.id)) }
        }
    }
    for (k, xs) in per {
        let s = xs.sorted { $0.0 < $1.0 }
        for (a, b) in zip(s, s.dropFirst()) {
            #expect(b.0 >= a.1.addingTimeInterval(3600), "cleaner \(k): job \(a.2) then job \(b.2)")
        }
    }
}

final class Fixture {
    let url: URL
    var store: CleaningStore

    init() throws {
        url = FileManager.default.temporaryDirectory.appendingPathComponent("hidden-\(UUID().uuidString)/data.json")
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        store = try CleaningStore(fileURL: url, timeZone: ZONE)
    }

    deinit { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }

    func reopen() throws { store = try CleaningStore(fileURL: url, timeZone: ZONE) }

    func cleaners(_ n: Int, first: Int = 0) throws -> [Int] { try (0..<n).map { try store.createCleaner(name: "Cleaner \(first + $0)").id } }
    func client(_ name: String = "Client A") throws -> Int { try store.createClient(name: name).id }
    func book(_ client: Int, _ n: Int, _ minutes: Int, _ day: String) throws -> Job {
        try store.bookJob(BookingRequest(clientId: client, cleanersNeeded: n, expectedLengthMinutes: minutes, requestedDay: TT.day(day)))
    }
    func job(_ id: Int) throws -> Job { try store.job(id: id) }
    func jobs(_ ids: [Int]) throws -> [Job] { try ids.map { try store.job(id: $0) } }
    /// what the store answers for these jobs and its records, and its file's bytes (which hold the
    /// invoices: the store's invoices() is milestone 2's, and this file must compile without it)
    func snapshot(_ ids: [Int]) -> String {
        let js = ids.map { (try? store.job(id: $0)).map(describe) ?? "none" }
        let file = (try? Data(contentsOf: url)) ?? Data()
        return "\(store.cleaners()) \(store.clients()) \(js) \(file.count) \(file.hashValue)"
    }

    /// the call throws CleaningError with a message, and changes nothing
    func refused(_ ids: [Int], _ what: String, _ f: () throws -> Void) -> String {
        let before = snapshot(ids)
        var message = ""
        do { try f(); Issue.record("\(what): expected an error") } catch let e as CleaningError { message = e.message } catch { Issue.record("\(what): \(error) is not a CleaningError") }
        #expect(!message.isEmpty, "\(what): the error has no message")
        #expect(snapshot(ids) == before, "\(what): something changed")
        return message
    }
}

@Test func cleanerAndClientRecords() throws {
    let f = try Fixture()
    let a = try f.store.createCleaner(name: "Ann"), b = try f.store.createCleaner(name: "Bo")
    #expect(a.name == "Ann" && a.id != b.id)
    #expect(try f.store.updateCleaner(id: a.id, name: "Anna").name == "Anna")
    #expect(f.store.cleaners().map(\.name) == ["Anna", "Bo"])
    _ = f.refused([], "a blank name") { _ = try f.store.createCleaner(name: "  ") }
    _ = f.refused([], "an unknown cleaner") { _ = try f.store.updateCleaner(id: 9999, name: "X") }
    try f.store.deleteCleaner(id: a.id)
    #expect(f.store.cleaners().map(\.name) == ["Bo"])
    _ = f.refused([], "deleting it again") { try f.store.deleteCleaner(id: a.id) }
    let k = try f.store.createClient(name: "Kim")
    _ = try f.store.createClient(name: "Lee")
    #expect(try f.store.updateClient(id: k.id, name: "Kimi").name == "Kimi")
    _ = f.refused([], "a blank client name") { _ = try f.store.updateClient(id: k.id, name: "") }
    try f.store.deleteClient(id: k.id)
    #expect(f.store.clients().map(\.name) == ["Lee"])
}

@Test func recordsAreKeptInTheFile() throws {
    let f = try Fixture()
    let a = try f.cleaners(1)[0]
    let j = try f.book(try f.client(), 1, 60, MON)
    try f.reopen()
    #expect(f.store.cleaners().map(\.id) == [a])
    #expect(describe(try f.job(j.id)) == describe(j))
}

@Test func shadowAfterAWholeHour() throws {
    // G1: a job ending 12:00 leaves 13:00 as the earliest next start, not 12:45
    let f = try Fixture()
    let a = try f.cleaners(1)[0], cl = try f.client()
    let j1 = try f.book(cl, 1, 240, MON)
    #expect(j1.cleanerIds == [a] && spans(j1) == ["\(MON)T08:00-\(MON)T12:00"] && j1.status == .booked && j1.invoiceId == nil)
    #expect(j1.parts[0].durationMinutes == 240)
    #expect(spans(try f.book(cl, 1, 60, MON)) == ["\(MON)T13:00-\(MON)T14:00"])
}

@Test func shadowToTheNextQuarterHour() throws {
    // G2: a job ending 12:10 leaves 13:15
    let f = try Fixture()
    _ = try f.cleaners(1); let cl = try f.client()
    #expect(spans(try f.book(cl, 1, 250, MON)) == ["\(MON)T08:00-\(MON)T12:10"])
    #expect(startOf(try f.book(cl, 1, 30, MON)) == "\(MON)T13:15")
}

@Test func aMinutePastTheHourIsInsideTheShadow() throws {
    let f = try Fixture()
    _ = try f.cleaners(1); let cl = try f.client()
    #expect(spans(try f.book(cl, 1, 241, MON)) == ["\(MON)T08:00-\(MON)T12:01"])
    #expect(startOf(try f.book(cl, 1, 30, MON)) == "\(MON)T13:15")     // 13:00 is 59 minutes after
}

@Test func saturdayGoesToMonday() throws {
    // G3
    let f = try Fixture()
    _ = try f.cleaners(1)
    let j = try f.book(try f.client(), 1, 120, SAT)
    #expect(spans(j) == ["\(NEXT_MON)T08:00-\(NEXT_MON)T10:00"])
    #expect(j.requestedDay.year == 2027 && j.requestedDay.month == 11 && j.requestedDay.day == 20)
}

@Test func aJobThatDoesNotFitGoesToTheNextWorkday() throws {
    let f = try Fixture()
    _ = try f.cleaners(1); let cl = try f.client()
    _ = try f.book(cl, 1, 420, MON)
    #expect(startOf(try f.book(cl, 1, 120, MON)) == "\(TUE)T08:00")
}

@Test func anEightHourJobIsOnePart() throws {
    // G4
    let f = try Fixture()
    _ = try f.cleaners(1)
    #expect(spans(try f.book(try f.client(), 1, 480, MON)) == ["\(MON)T08:00-\(MON)T16:00"])
}

@Test func aTenHourJobSplitsAcrossTwoWorkdays() throws {
    // G5: 8 h on the first workday, 2 h on the next, the same crew
    let f = try Fixture()
    _ = try f.cleaners(3); let cl = try f.client()
    let j = try f.book(cl, 2, 600, MON)
    #expect(spans(j) == ["\(MON)T08:00-\(MON)T16:00", "\(TUE)T08:00-\(TUE)T10:00"])
    #expect(j.parts.map(\.durationMinutes) == [480, 120] && Set(j.cleanerIds).count == 2)
    let fr = try f.book(cl, 1, 600, FRI)
    #expect(spans(fr) == ["\(FRI)T08:00-\(FRI)T16:00", "\(NEXT_MON)T08:00-\(NEXT_MON)T10:00"])
    assertNoOverlaps(try f.jobs([j.id, fr.id]))
}

@Test func cleanersAssignedByTheSystem() throws {
    let f = try Fixture()
    let cs = try f.cleaners(3), cl = try f.client()
    var ids = [Int]()
    for n in 1...3 {
        let j = try f.book(cl, n, 60, MON)
        #expect(j.cleanerIds.count == n && Set(j.cleanerIds).isSubset(of: cs))
        ids.append(j.id)
    }
    for _ in 0..<6 { ids.append(try f.book(cl, 2, 90, MON).id) }
    assertNoOverlaps(try f.jobs(ids))
}

@Test func theNinetyDaySearch() throws {
    // G6: one cleaner and eight-hour jobs: a weekday each. Monday to Monday + 90 days holds 65.
    let f = try Fixture()
    _ = try f.cleaners(1); let cl = try f.client()
    var ids = [Int](), last: Job? = nil
    for _ in 0..<65 { last = try f.book(cl, 1, 480, MON); ids.append(last!.id) }
    #expect(String(startOf(last!).prefix(10)) == TT.plus(MON, days: 88))
    let m = f.refused(ids, "a 66th job") { _ = try f.book(cl, 1, 480, MON) }
    #expect(m.contains(NO_SLOT))
    #expect((try? f.store.job(id: ids.max()! + 1)) == nil)
}

@Test func badBookingRequestsChangeNothing() throws {
    let f = try Fixture()
    _ = try f.cleaners(2); let cl = try f.client()
    let j = try f.book(cl, 1, 60, MON)
    _ = f.refused([j.id], "3 cleaners of 2") { _ = try f.book(cl, 3, 60, MON) }
    _ = f.refused([j.id], "0 cleaners") { _ = try f.book(cl, 0, 60, MON) }
    _ = f.refused([j.id], "4 cleaners") { _ = try f.book(cl, 4, 60, MON) }
    _ = f.refused([j.id], "0 minutes") { _ = try f.book(cl, 1, 0, MON) }
    _ = f.refused([j.id], "an unknown client") { _ = try f.book(9999, 1, 60, MON) }
    _ = f.refused([j.id], "an unknown job") { _ = try f.store.job(id: 9999) }
}
