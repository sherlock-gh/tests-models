# Setup notes

The amended plan is in `plan/`; the original repository `plan/` is unchanged. These are details the plan did not completely specify and the kit had to choose:

- Swift `Day` is a `String` alias holding `YYYY-MM-DD`; the contract named the type but did not define it. Swift errors use `ErrorKind.BadInput`, `.NotFound`, `.RuleViolation` and carry a message.
- Fractional `expected_length_hours` becomes whole minutes, rounding upward when not already within floating-point tolerance of a whole minute. Neither app's booking algorithm uses sub-minute slots. Tests only use minute-exact lengths.
- A tap on a split job is routed to the assignment on the tap's calendar day; when no part falls on that day, the first unfinished assignment is used. Tests tap on booked part days.
- The 90-day horizon includes the requested date and day 90. A later split part must be on a later weekday, but need not be the immediately following weekday if the booking rule finds no place there.
- Swift's `depart` returns `JobWithInvoice?` containing the updated job and an optional newly issued invoice; the contract named the return type but did not define its fields.
- Local test dates use November 15–22, 2027, away from clock changes. The plan specifies America/Los_Angeles; the fixture supplies it explicitly in Swift and the desktop uses its default.
- Hidden Python tests call `create_app(data_file).request(method, path, body)` in-process. The plan calls for no loopback dependency; the contract specifies the HTTP JSON shapes, not an in-process invocation name. They check statuses and envelopes at the handler boundary.
- The harness had to run `swift test --disable-sandbox` in cloned directories: nested SwiftPM sandboxing prevented its manifest from compiling here. It also now recognizes Swift Testing's success summary rather than only XCTest's.
- The reference currently uses a fallback label for a cleaner removed after they arrived but before invoice issue; the plan does not say how to retain a deleted cleaner's name for the later immutable invoice without adding an archive field to the prescribed file layout. This edge remains unresolved.
