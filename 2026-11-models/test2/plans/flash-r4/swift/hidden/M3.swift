import Foundation
import Testing
import CleaningLogic

@Test func extensionMovesLaterJob() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let first = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 4, requestedDay: monday)
    let later = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    _ = try app.arrive(jobId: first.id, cleanerId: a.id, at: moment(monday + "T08:00"))
    var result: ExtensionResult?
    for _ in 0..<3 { result = try app.extend(jobId: first.id, cleanerId: a.id, at: moment(monday + "T11:00")) }
    #expect(result?.job.parts[0].assignments[0].extendedMinutes == 60)
    #expect(try app.readJob(id: later.id).parts[0].start >= monday + "T14:00")
    _ = try app.depart(jobId: first.id, cleanerId: a.id, at: moment(monday + "T12:00"))
    reject(app) { _ = try app.extend(jobId: first.id, cleanerId: a.id, at: moment(monday + "T12:30")) }
}
@Test func extensionMovesCoworkersLaterJob() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let b = try app.createCleaner(name: "Bo", phone: "555", email: "b@c")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let first = try app.bookJob(clientId: c.id, cleanersNeeded: 2, expectedLengthHours: 4, requestedDay: monday)
    let later = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    #expect(later.parts[0].assignments[0].cleanerId == a.id)
    _ = try app.arrive(jobId: first.id, cleanerId: b.id, at: moment(monday + "T08:00"))
    for _ in 0..<3 { _ = try app.extend(jobId: first.id, cleanerId: b.id, at: moment(monday + "T11:00")) }
    #expect(try app.readJob(id: later.id).parts[0].start >= monday + "T14:00")
}
