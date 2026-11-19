import Foundation
import Testing
import CleaningLogic

@Test func tapInvoicePayment() throws {
    let app = fixture()
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let b = try app.createCleaner(name: "Bo", phone: "555", email: "b@c")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let j = try app.bookJob(clientId: c.id, cleanersNeeded: 2, expectedLengthHours: 4, requestedDay: monday)
    #expect(app.daySchedule(cleanerId: a.id, on: monday).count == 1)
    reject(app) { _ = try app.depart(jobId: j.id, cleanerId: a.id, at: moment(monday + "T11:30")) }
    _ = try app.arrive(jobId: j.id, cleanerId: a.id, at: moment(monday + "T08:00"))
    reject(app) { _ = try app.arrive(jobId: j.id, cleanerId: a.id, at: moment(monday + "T09:00")) }
    _ = try app.depart(jobId: j.id, cleanerId: a.id, at: moment(monday + "T11:30"))
    #expect(app.listInvoices().isEmpty)
    _ = try app.arrive(jobId: j.id, cleanerId: b.id, at: moment(monday + "T08:00"))
    let done = try app.depart(jobId: j.id, cleanerId: b.id, at: moment(monday + "T12:00"))
    let bill = try #require(done?.invoice)
    #expect(bill.totalCents == 33750)
    #expect(Set(bill.lines.map(\.amountCents)) == Set([15750, 18000]))
    #expect(Set(bill.lines.map(\.minutesWorked)) == Set([210, 240]))
    reject(app) { _ = try app.recordPayment(invoiceId: bill.id, amountCents: 33700) }
    #expect(app.listInvoices(settled: false).count == 1)
    #expect(try app.recordPayment(invoiceId: bill.id, amountCents: 33750).settled)
}
