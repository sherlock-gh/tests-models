import Foundation
import Testing
import CleaningLogic

@Test func removalAndInvoiceGuard() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let b = try app.createCleaner(name: "Bo", phone: "555", email: "b@c")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let j1 = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    let moved = try app.deleteCleaner(id: a.id)
    #expect(moved.rebookedJobIds == [j1.id])
    #expect(try app.readJob(id: j1.id).parts[0].assignments[0].cleanerId == b.id)
    _ = try app.arrive(jobId: j1.id, cleanerId: b.id, at: moment(monday + "T08:00"))
    _ = try app.depart(jobId: j1.id, cleanerId: b.id, at: moment(monday + "T09:00"))
    reject(app) { try app.deleteJob(id: j1.id) }
    let j2 = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    #expect(try app.deleteClient(id: c.id).cancelledJobIds == [j2.id])
    #expect(try app.readJob(id: j2.id).status == "cancelled")
    reject(app) { _ = try app.readCleaner(id: 9999) }
}

@Test func jobEditDoesNotMoveTheBooking() throws {
    let app = fixture()
    _ = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let first = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    _ = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 1, requestedDay: monday)
    reject(app) { _ = try app.updateJob(id: first.id, clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 2, requestedDay: monday) }
    let edited = try app.updateJob(id: first.id, clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 0.5, requestedDay: monday)
    #expect(edited.parts[0].start == first.parts[0].start)
    #expect(edited.parts[0].end == monday + "T08:30")
}
