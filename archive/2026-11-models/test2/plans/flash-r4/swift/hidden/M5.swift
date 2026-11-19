import Foundation
import Testing
import CleaningLogic

@Test func utilizationAndPersistence() throws {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("flash-r4-\(UUID().uuidString)/data.json")
    let app = CleaningApp(dataFileURL: url)
    let a = try app.createCleaner(name: "Ann", phone: "555", email: "a@b")
    let c = try app.createClient(name: "Pat", address: "1 Main", phone: "555")
    let j = try app.bookJob(clientId: c.id, cleanersNeeded: 1, expectedLengthHours: 8, requestedDay: monday)
    _ = try app.arrive(jobId: j.id, cleanerId: a.id, at: moment(monday + "T08:00"))
    _ = try app.depart(jobId: j.id, cleanerId: a.id, at: moment(monday + "T17:00"))
    let report = app.utilization(cleanerId: a.id, from: monday, to: tuesday)
    #expect(report.days.first?.minutes == 540)
    #expect(report.days.first?.of == 480)
    #expect(report.weeks.first?.minutes == 540)
    let restarted = CleaningApp(dataFileURL: url)
    #expect(restarted.listInvoices().first?.totalCents == 40500)
    #expect(try restarted.readJob(id: j.id).invoiceId != nil)
}
