import Foundation
import Testing
import CleaningLogic

let monday = "2027-11-15", tuesday = "2027-11-16", saturday = "2027-11-20", nextMonday = "2027-11-22"
let zone = TimeZone(identifier: "America/Los_Angeles")!
func moment(_ value: String) -> Date {
    let f = DateFormatter(); f.timeZone = zone; f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd'T'HH:mm"
    return f.date(from: value)!
}
func fixture() -> CleaningApp {
    CleaningApp(dataFileURL: FileManager.default.temporaryDirectory.appendingPathComponent("flash-r4-\(UUID().uuidString)/data.json"))
}
func reject(_ app: CleaningApp, _ action: () throws -> Void) {
    do { try action(); Issue.record("expected AppError") }
    catch let error as AppError { #expect(!error.message.isEmpty) }
    catch { Issue.record("wrong error: \(error)") }
}
@Test func bookingsAndReplacement() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let b = try app.createCleaner(name: "Bo", phone: "555", email: "b@c")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let first = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 8, requestedDay: monday)
    #expect(first.parts[0].start == monday + "T08:00")
    #expect(first.parts[0].assignments[0].cleanerId == a.id)
    let second = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 10, requestedDay: monday)
    #expect(second.parts.map(\.day) == [monday, tuesday])
    #expect(second.parts[0].assignments[0].cleanerId == b.id)
    #expect(second.parts[1].assignments.count == 1)
    let weekend = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: saturday)
    #expect(weekend.parts[0].start == nextMonday + "T08:00")
    reject(app) { _ = try app.bookJob(clientId: c.id, cleanersNeeded: 0, expectedLengthHours: 1, requestedDay: monday) }
    reject(app) { _ = try app.bookJob(clientId: 9999, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday) }
}
@Test func oneHourShadow() throws {
    let app = fixture(); _ = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let a = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 250.0 / 60, requestedDay: monday)
    #expect(a.parts[0].end == monday + "T12:10")
    let b = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 0.5, requestedDay: monday)
    #expect(b.parts[0].start == monday + "T13:15")
}
@Test func laterPartUsesReplacementCleaner() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let b = try app.createCleaner(name: "Bo", phone: "555", email: "b@c")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let busy = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 8, requestedDay: tuesday)
    #expect(busy.parts[0].assignments[0].cleanerId == a.id)
    let split = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 10, requestedDay: monday)
    #expect(split.parts[0].assignments[0].cleanerId == a.id)
    #expect(split.parts[1].day == tuesday)
    #expect(split.parts[1].assignments[0].cleanerId == b.id)
}

@Test func strictHourFromOneMinutePastNoon() throws {
    let app = fixture(); _ = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let a = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 241.0 / 60, requestedDay: monday)
    #expect(a.parts[0].end == monday + "T12:01")
    let b = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 0.5, requestedDay: monday)
    #expect(b.parts[0].start == monday + "T13:15")
}
