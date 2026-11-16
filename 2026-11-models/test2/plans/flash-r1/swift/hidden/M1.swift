// Milestone 1 (Flash-Next's plan): records and booking (US1), through Store
// (contracts/cleaner-logic-swift.md, exact-interfaces.md). Monday 2027-11-15 is the first test day.
// Times are local, as the plan says.
import Foundation
import Testing
import CleaningLogic

let MON = "2027-11-15", TUE = "2027-11-16", FRI = "2027-11-19", SAT = "2027-11-20", NEXT_MON = "2027-11-22"

enum TestTime {
    static let fmt: DateFormatter = {
        let f = DateFormatter(); f.calendar = Calendar.current; f.timeZone = TimeZone.current
        f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd'T'HH:mm"; return f
    }()
    static func day(_ s: String) -> Date { fmt.date(from: s + "T00:00")! }
    static func at(_ day: String, _ hm: String) -> Date { fmt.date(from: "\(day)T\(hm)")! }
    static func string(_ d: Date) -> String { fmt.string(from: d) }
    /// (day, minute of the day) of a time
    static func slot(_ d: Date) -> (String, Int) {
        let s = string(d), hm = s.split(separator: "T")[1].split(separator: ":")
        return (String(s.prefix(10)), Int(hm[0])! * 60 + Int(hm[1])!)
    }
}

func same<T: Equatable>(_ a: T, _ b: T) -> Bool { a == b }
func slot(_ j: Job) -> String { let (d, m) = TestTime.slot(j.bookedStart); return "\(d) \(m)" }
func slot(_ d: String, _ m: Int) -> String { "\(d) \(m)" }
func cleanersOf(_ j: Job) -> [Int] { j.assignments.map(\.cleanerID).sorted() }   // the plan leaves their order open

func code(_ e: CleaningError) -> String {
    switch e {
    case .notFound: return "notFound"
    case .invalidInput: return "invalidInput"
    case .jobTooLong: return "jobTooLong"
    case .noFeasibleSlot: return "noFeasibleSlot"
    case .tapOutOfOrder: return "tapOutOfOrder"
    case .wrongCleaner: return "wrongCleaner"
    case .paymentAmountMismatch: return "paymentAmountMismatch"
    case .alreadySettled: return "alreadySettled"
    case .notEnoughCleaners: return "notEnoughCleaners"
    @unknown default: return "\(e)"
    }
}

func describe(_ j: Job) -> String {
    let a = j.assignments.sorted { $0.cleanerID < $1.cleanerID }.map {
        "\($0.cleanerID) \($0.arrival.map(TestTime.string) ?? "-") \($0.departure.map(TestTime.string) ?? "-") \($0.workedMinutes ?? -1)"
    }
    return "\(j.id) \(j.clientID) \(TestTime.string(j.requestedDay).prefix(10)) \(j.expectedLengthMinutes) \(j.cleanersRequired) "
        + "\(TestTime.string(j.bookedStart)) \(TestTime.string(j.bookedEnd)) \(j.state) \(a) \(j.invoiceID ?? -1)"
}

func describe(_ i: Invoice) -> String {
    let l = i.lines.sorted { $0.cleanerID < $1.cleanerID }.map { "\($0.cleanerID) \($0.workedMinutes) \($0.amount)" }
    return "\(i.id) \(i.jobID) \(TestTime.string(i.issuedAt)) \(l) \(i.total) \(i.settled) \(i.paymentAmount.map { "\($0)" } ?? "-") \(i.paymentDate.map(TestTime.string) ?? "-")"
}

class Fixture {
    let url: URL
    var store: Store

    init() throws {
        url = FileManager.default.temporaryDirectory.appendingPathComponent("hidden-\(UUID().uuidString)/store.json")
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        store = try Store(fileURL: url)
    }

    deinit { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }

    func reopen() throws { store = try Store(fileURL: url) }

    func cleaners(_ n: Int) throws -> [Int] { try (0..<n).map { try store.addCleaner(name: "Cleaner \($0)").id }.sorted() }
    func client(_ name: String = "Client A") throws -> Int { try store.addClient(name: name).id }
    func book(_ client: Int, _ n: Int, _ hours: Double, _ day: String) throws -> Job {
        try store.bookJob(clientID: client, cleanersRequired: n, expectedLength: hours, requestedDay: TestTime.day(day))
    }
    func job(_ id: Int) -> Job { store.job(id: id)! }

    /// Every job and invoice the store answers for, by id (ids are sequence numbers, data-model.md)
    func snapshot() -> [String] {
        (0...80).compactMap { store.job(id: $0) }.map { describe($0) + " | " + (store.invoice(forJob: $0.id).map(describe) ?? "-") }
    }

    /// The call throws a CleaningError (one of codes, where the plan says which) and changes nothing.
    func fails<T>(_ codes: [String] = [], _ body: () throws -> T) {
        let before = snapshot()
        do {
            _ = try body()
            Issue.record(Comment(rawValue: "expected an error"))
        } catch let e as CleaningError {
            #expect(codes.isEmpty || codes.contains(code(e)), Comment(rawValue: "\(e)"))
        } catch {
            Issue.record(Comment(rawValue: "expected a CleaningError, got \(error)"))
        }
        #expect(same(snapshot(), before), Comment(rawValue: "an error changed the data"))
    }
}

func assertNoOverlaps(_ jobs: [Job]) {
    var per = [String: [(Int, Int)]]()
    for j in jobs where j.state == "scheduled" {
        let (d, s) = TestTime.slot(j.bookedStart), e = s + j.expectedLengthMinutes
        #expect(s >= 480 && e <= 1020, Comment(rawValue: describe(j)))
        for c in cleanersOf(j) { per["\(c) \(d)", default: []].append((s, e)) }
    }
    for (k, xs) in per {
        let s = xs.sorted { $0.0 < $1.0 }
        for (a, b) in zip(s, s.dropFirst()) { #expect(b.0 >= a.1 + 60, Comment(rawValue: "\(k): \(a) then \(b)")) }
    }
}

@Suite struct M1Records {
    @Test func cleanerAndClientRecords() throws {
        let f = try Fixture()
        var c = try f.store.addCleaner(name: "  Ana  ")
        #expect(c.name == "Ana")                                        // trimmed
        c.name = "Ana B"
        try f.store.updateCleaner(c)
        var k = try f.store.addClient(name: "Home 1")
        k.name = "Home 2"
        try f.store.updateClient(k)
        let j = try f.book(k.id, 1, 1, MON)
        #expect(same(j.clientID, k.id) && cleanersOf(j) == [c.id])
        try f.store.deleteClient(id: k.id)
        f.fails(["notFound"]) { try f.store.updateClient(k) }
        let d = try f.store.addCleaner(name: "Bo")
        try f.store.deleteCleaner(id: d.id)                            // no future jobs: plain deletion
        f.fails(["notFound"]) { try f.store.updateCleaner(d) }
    }

    @Test func badInputChangesNothing() throws {
        let f = try Fixture()
        let ids = try f.cleaners(2)
        let cl = try f.client()
        f.fails(["invalidInput"]) { try f.store.addCleaner(name: "   ") }
        f.fails(["invalidInput"]) { try f.store.addClient(name: "") }
        f.fails(["notFound"]) { try f.store.deleteCleaner(id: 9999) }
        f.fails(["notFound"]) { try f.book(9999, 1, 1, MON) }
        f.fails(["jobTooLong"]) { try f.book(cl, 1, 9.25, MON) }
        for (n, h) in [(1, 0.0), (1, -1.0), (0, 1.0), (4, 1.0)] { f.fails(["invalidInput"]) { try f.book(cl, n, h, MON) } }
        f.fails(["noFeasibleSlot"]) { try f.book(cl, 3, 1, MON) }
        #expect(ids.count == 2)
    }

    @Test func firstBooking() throws {
        let f = try Fixture()
        let ids = try f.cleaners(12)
        let j = try f.book(try f.client(), 2, 4, MON)
        #expect(same(TestTime.string(j.bookedStart), "\(MON)T08:00") && same(TestTime.string(j.bookedEnd), "\(MON)T12:00"))
        #expect(same(j.state, "scheduled") && same(j.expectedLengthMinutes, 240) && same(j.cleanersRequired, 2))
        #expect(same(cleanersOf(j), Array(ids[0..<2])))
        #expect(same(describe(f.job(j.id)), describe(j)))
    }

    @Test func oneHourGapToTheMinute() throws {
        let f = try Fixture()
        _ = try f.cleaners(1)
        let cl = try f.client()
        _ = try f.book(cl, 1, 4, MON)                                   // 8:00-12:00
        #expect(same(slot(try f.book(cl, 1, 2, MON)), slot(MON, 780)))  // 13:00
        _ = try f.book(cl, 1, 0.25, TUE)                                // 8:00-8:15
        #expect(same(slot(try f.book(cl, 1, 1, TUE)), slot(TUE, 555)))  // 9:15
    }

    @Test func weekendsFullDaysAndFive() throws {
        let f = try Fixture()
        _ = try f.cleaners(1)
        let cl = try f.client()
        #expect(same(slot(try f.book(cl, 1, 1, SAT)), slot(NEXT_MON, 480)))
        let full = try f.book(cl, 1, 9, FRI)
        #expect(same(TestTime.string(full.bookedEnd), "\(FRI)T17:00"))
        #expect(same(slot(try f.book(cl, 1, 1, FRI)), slot(NEXT_MON, 600)))
        _ = try f.book(cl, 1, 5, MON)                                   // 8:00-13:00
        #expect(same(slot(try f.book(cl, 1, 4, MON)), slot(TUE, 480)))  // 14:00 + 4 h passes 17:00
    }

    @Test func severalCleanersNeedACommonStart() throws {
        let f = try Fixture()
        let ids = try f.cleaners(3)
        let cl = try f.client()
        _ = try f.book(cl, 2, 4, MON)                                   // a, b 8:00-12:00
        let j = try f.book(cl, 2, 2, MON)                               // only c free at 8:00
        #expect(same(slot(j), slot(MON, 780)) && same(cleanersOf(j), Array(ids[0..<2])))
    }

    @Test func savedDataSurvives() throws {
        let f = try Fixture()
        _ = try f.cleaners(3)
        _ = try f.book(try f.client(), 2, 3.5, MON)
        let before = f.snapshot()
        try f.store.save()
        try f.reopen()
        #expect(same(f.snapshot(), before))
        _ = try f.cleaners(1)                                           // the reopened store goes on from there
        #expect(same(slot(try f.book(try f.client(), 2, 1, MON)), slot(MON, 480)))
    }

    @Test func randomWorkloadMatchesTheRule() throws {
        let f = try Fixture()
        let ids = try f.cleaners(12)
        let cls = try (0..<5).map { try f.client("Client \($0)") }
        var rnd = Seeded(20271115)
        var mine = [Job]()
        for _ in 0..<60 {
            let n = [1, 1, 2, 3].randomElement(using: &rnd)!, quarters = Int.random(in: 2...36, using: &rnd)
            let req = TestTime.string(Calendar.current.date(byAdding: .day, value: Int.random(in: 0..<10, using: &rnd), to: TestTime.day(MON))!).prefix(10)
            let want = oracle(mine.map { f.job($0.id) }, ids, n, quarters * 15, String(req))
            let j = try f.book(cls.randomElement(using: &rnd)!, n, Double(quarters) / 4, String(req))
            #expect(same(slot(j), want.0) && same(cleanersOf(j), want.1), Comment(rawValue: "\(n) \(quarters) \(req)"))
            mine.append(j)
        }
        assertNoOverlaps(mine.map { f.job($0.id) })
    }
}

/// The same workload every run
struct Seeded: RandomNumberGenerator {
    var x: UInt64
    init(_ seed: UInt64) { x = seed }
    mutating func next() -> UInt64 { x = x &* 6364136223846793005 &+ 1442695040888963407; return x }
}

/// A minute-by-minute scan of the booking rule (research D-3): earliest weekday start, lowest-id cleaners.
func oracle(_ jobs: [Job], _ ids: [Int], _ n: Int, _ mins: Int, _ requested: String) -> (String, [Int]) {
    var d = TestTime.day(requested)
    while true {
        let wd = Calendar.current.component(.weekday, from: d)
        if wd != 1 && wd != 7 {
            let day = String(TestTime.string(d).prefix(10))
            let busy = jobs.filter { $0.state == "scheduled" && TestTime.slot($0.bookedStart).0 == day }
                .map { (cleanersOf($0), TestTime.slot($0.bookedStart).1, TestTime.slot($0.bookedStart).1 + $0.expectedLengthMinutes) }
            for s in 480...(1020 - mins) {
                let ok = ids.filter { c in busy.allSatisfy { !$0.0.contains(c) || $0.1 >= s + mins + 60 || s >= $0.2 + 60 } }
                if ok.count >= n { return (slot(day, s), Array(ok.prefix(n))) }
            }
        }
        d = Calendar.current.date(byAdding: .day, value: 1, to: d)!
    }
}
