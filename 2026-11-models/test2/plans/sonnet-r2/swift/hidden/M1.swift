// Milestone 1: records and booking (plan US1, US2; conformance C1-C7), through CleaningService
// (plan contracts/interfaces.md). Monday 2026-11-16 is the first test day.
import Foundation
import Testing
import CleaningCore

let MON = "2026-11-16", TUE = "2026-11-17", FRI = "2026-11-20", SAT = "2026-11-21", NEXT_MON = "2026-11-23"

/// The tests' own dates: day numbers from 2026-11-16 (a Monday), in UTC
enum TestDates {
    static let cal: Calendar = { var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "UTC")!; return c }()
    static let fmt: DateFormatter = {
        let f = DateFormatter(); f.calendar = cal; f.timeZone = cal.timeZone; f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"; return f
    }()
    static let base = fmt.date(from: MON)!
    static func number(_ s: String) -> Int { cal.dateComponents([.day], from: base, to: fmt.date(from: s)!).day! }
    static func string(_ n: Int) -> String { fmt.string(from: cal.date(byAdding: .day, value: n, to: base)!) }
    static func weekday(_ n: Int) -> Int { ((n % 7) + 7) % 7 }   // 0 = Monday
}

func same<T: Equatable>(_ a: T, _ b: T) -> Bool { a == b }

class Fixture {
    var url: URL!
    var svc: CleaningService!

    init() throws {
        url = FileManager.default.temporaryDirectory.appendingPathComponent("hidden-\(UUID().uuidString)/data.json")
        // The folder exists, the file doesn't: the plans say nothing of creating folders
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        svc = try CleaningService(storeURL: url)
    }

    deinit {
        try? FileManager.default.removeItem(at: url.deletingLastPathComponent())
    }

    func cleaners(_ n: Int) throws -> [Int] { try (0..<n).map { try svc.createCleaner(name: "Cleaner \($0)").id }.sorted() }
    func client(_ name: String = "Client A") throws -> Int { try svc.createClient(name: name, address: "1 Synthetic St").id }
    func book(_ client: Int, _ needed: Int, _ length: Int, _ day: String) throws -> Job {
        try svc.bookJob(clientId: client, cleanersNeeded: needed, lengthMinutes: length, requestedDate: day)
    }
    // Milestone 1's records only: invoices come in a later milestone (later tests compare them themselves)
    struct Snapshot: Equatable { let cleaners: [Cleaner]; let clients: [Client]; let jobs: [Job] }
    func snapshot() -> Snapshot { Snapshot(cleaners: svc.listCleaners(), clients: svc.listClients(), jobs: svc.listJobs()) }

    /// The call throws a CleaningError (with this code, if given) and changes nothing.
    func fails<T>(_ codes: [String] = [], _ body: () throws -> T) {   // any of codes, where the plan doesn't say which
        let before = snapshot()
        do {
            _ = try body()
            Issue.record(Comment(rawValue: "expected an error"))
        } catch let e as CleaningError {
            #expect(codes.isEmpty || codes.contains(e.code), Comment(rawValue: "\(e.code): \(e.message)"))
            #expect(!(e.message.isEmpty))
        } catch {
            Issue.record(Comment(rawValue: "expected a CleaningError, got \(error)"))
        }
        #expect(same(snapshot(), before), Comment(rawValue: "an error changed the data"))
    }

    func assertNoOverlaps() {
        var per = [String: [Job]]()
        for j in svc.listJobs() where j.status != "cancelled" {
            #expect(same(Set(j.cleanerIds).count, j.cleanersNeeded))
            for c in j.cleanerIds { per["\(c) \(j.date)", default: []].append(j) }
        }
        for (k, js) in per {
            let s = js.sorted { $0.startMinute < $1.startMinute }
            for (a, b) in zip(s, s.dropFirst()) {
                #expect((b.startMinute) >= (a.endMinute + 60), Comment(rawValue: "\(k): \(a.id) then \(b.id)"))
            }
        }
    }
}

@Suite(.serialized) final class M1RecordsTests: Fixture {
    @Test func testCleanerCRUD() throws {
        let c = try svc.createCleaner(name: "Ana")
        #expect(same(try svc.getCleaner(id: c.id), c))
        #expect(same(try svc.updateCleaner(id: c.id, name: "Ana B").name, "Ana B"))
        #expect(same(svc.listCleaners().map { $0.name }, ["Ana B"]))
        try svc.deleteCleaner(id: c.id)
        fails(["not_found"]) { try svc.getCleaner(id: c.id) }
    }

    @Test func testClientCRUD() throws {
        let c = try svc.createClient(name: "Home 1", address: "2 Fake Rd")
        #expect(same(try svc.getClient(id: c.id), c))
        let u = try svc.updateClient(id: c.id, name: "Home 2", address: nil)
        #expect(same(u.name, "Home 2"))
        #expect((u.address) == nil)
        try svc.deleteClient(id: c.id)
        fails(["not_found"]) { try svc.getClient(id: c.id) }
    }

    @Test func testBadInputChangesNothing() throws {
        _ = try cleaners(2)
        let cl = try client()
        fails(["invalid_input"]) { try svc.createCleaner(name: "  ") }
        fails(["invalid_input"]) { try svc.createClient(name: "", address: nil) }
        fails(["not_found"]) { try svc.updateClient(id: 9999, name: "x", address: nil) }
        fails(["not_found", "invalid_input"]) { try book(9999, 1, 60, MON) }
        fails(["invalid_input"]) { try book(cl, 1, 60, "16/11/2026") }
    }

    @Test func testDataSurvivesANewService() throws {
        _ = try cleaners(3)
        _ = try book(try client(), 2, 200, MON)
        let before = snapshot()
        svc = try CleaningService(storeURL: url)
        #expect(same(snapshot(), before))
    }
}

@Suite(.serialized) final class M1BookingTests: Fixture {
    @Test func testC1FirstBooking() throws {
        let ids = try cleaners(12)
        let j = try book(try client(), 2, 240, MON)
        #expect(same([j.date, "\(j.startMinute)", "\(j.endMinute)", j.status], [MON, "480", "720", "booked"]))
        #expect(same(j.cleanerIds, Array(ids.prefix(2))))
        #expect(same(try svc.getJob(id: j.id), j))
    }

    @Test func testC2OneHourGapAndNoGrid() throws {
        _ = try cleaners(1)
        let cl = try client()
        _ = try book(cl, 1, 247, MON)                       // ends 12:07
        #expect(same(try book(cl, 1, 60, MON).startMinute, 787))
    }

    @Test func testC3C4C5WeekendsAndFullDays() throws {
        _ = try cleaners(1)
        let cl = try client()
        #expect(same(try book(cl, 1, 60, SAT).date, NEXT_MON))
        let full = try book(cl, 1, 540, FRI)
        #expect(same([full.date, "\(full.startMinute)", "\(full.endMinute)"], [FRI, "480", "1020"]))
        let n = try book(cl, 1, 60, FRI)
        #expect(same([n.date, "\(n.startMinute)"], [NEXT_MON, "600"]))
    }

    @Test func testSlotMustEndByFive() throws {
        _ = try cleaners(1)
        let cl = try client()
        _ = try book(cl, 1, 300, MON)
        let j = try book(cl, 1, 240, MON)
        #expect(same([j.date, "\(j.startMinute)"], [TUE, "480"]))
    }

    @Test func testC4C6Refusals() throws {
        _ = try cleaners(2)
        let cl = try client()
        for (n, l) in [(1, 541), (1, 0), (1, -5), (0, 60), (4, 60)] { fails(["invalid_input"]) { try book(cl, n, l, MON) } }
        fails(["unschedulable"]) { try book(cl, 3, 60, MON) }
    }

    @Test func testSeveralCleanersNeedACommonStart() throws {
        let ids = try cleaners(3)
        let cl = try client()
        _ = try book(cl, 2, 240, MON)
        let j = try book(cl, 2, 120, MON)
        #expect(same(j.startMinute, 780))
        #expect(same(j.cleanerIds, [ids[0], ids[1]]))
    }

    @Test func testClientDeleteCancelsBookedJobs() throws {
        _ = try cleaners(1)
        let keep = try client("Keep"), gone = try client("Gone")
        let j = try book(gone, 1, 240, MON)
        try svc.deleteClient(id: gone)
        #expect(same(try svc.getJob(id: j.id).status, "cancelled"))
        #expect(same(try book(keep, 1, 240, MON).startMinute, 480))
    }

    @Test func testC7CleanerDeleteRebooks() throws {
        let ids = try cleaners(2)
        let j = try book(try client(), 1, 240, MON)
        #expect(same(j.cleanerIds, [ids[0]]))
        try svc.deleteCleaner(id: ids[0])
        let k = try svc.getJob(id: j.id)
        #expect(same([k.date, "\(k.startMinute)", k.status], [MON, "480", "booked"]))
        #expect(same(k.cleanerIds, [ids[1]]))
    }

    @Test func testCleanerDeleteRefusedWhenAJobCannotBeRebooked() throws {
        let ids = try cleaners(1)
        _ = try book(try client(), 1, 240, MON)
        fails(["unschedulable"]) { try svc.deleteCleaner(id: ids[0]) }
    }

    @Test func testJobUpdateRebooksAndDelete() throws {
        _ = try cleaners(1)
        let cl = try client()
        let j1 = try book(cl, 1, 240, MON)
        let j2 = try book(cl, 1, 120, MON)
        let u = try svc.updateJob(id: j2.id, clientId: nil, cleanersNeeded: nil, lengthMinutes: nil, requestedDate: TUE)
        #expect(same([u.date, "\(u.startMinute)", u.requestedDate], [TUE, "480", TUE]))
        try svc.deleteJob(id: j1.id)
        if let gone = try? svc.getJob(id: j1.id) { #expect(gone.status == "cancelled") }   // deleted: gone, or kept as cancelled
        #expect(same(try book(cl, 1, 60, MON).startMinute, 480))
    }

    /// Per-minute scan of the booking rule, for the random workload
    func oracle(_ needed: Int, _ length: Int, _ requested: String, _ ids: [Int]) -> (String, Int, [Int]) {
        var d = TestDates.number(requested)
        while true {
            if TestDates.weekday(d) < 5 {
                let day = TestDates.string(d)
                let busy = svc.listJobs().filter { $0.status != "cancelled" && $0.date == day }
                for s in 480...(1020 - length) {
                    let ok = ids.filter { c in busy.allSatisfy { !$0.cleanerIds.contains(c) || $0.endMinute + 60 <= s || $0.startMinute >= s + length + 60 } }
                    if ok.count >= needed { return (day, s, Array(ok.prefix(needed))) }
                }
            }
            d += 1
        }
    }

    @Test func testRandomWorkloadMatchesTheRule() throws {
        var seed: UInt64 = 20261116
        func next(_ n: Int) -> Int { seed = seed &* 6364136223846793005 &+ 1442695040888963407; return Int((seed >> 33) % UInt64(n)) }
        let ids = try cleaners(12)
        let cls = try (0..<5).map { try client("Client \($0)") }
        for _ in 0..<70 {
            let needed = [1, 1, 2, 3][next(4)]
            let length = 30 + next(511)
            let req = TestDates.string(next(10))
            let want = oracle(needed, length, req, ids)
            let j = try book(cls[next(5)], needed, length, req)
            #expect(same([j.date, "\(j.startMinute)", "\(j.cleanerIds)"], [want.0, "\(want.1)", "\(want.2)"]), Comment(rawValue: "\(needed) \(length) \(req)"))
        }
        assertNoOverlaps()
    }
}
