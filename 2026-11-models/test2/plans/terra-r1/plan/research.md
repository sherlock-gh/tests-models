# Research: Cleaning Scheduling and Billing

## Runtime and interfaces

**Decision**: Implement the back office as a Python 3.11+ standard-library local HTTP server and browser UI, and the cleaner expression as a Swift 5.9+ package exposing callable application logic without a UI. Keep their data stores independent. Use Python `unittest` and Swift XCTest for automated tests.

**Rationale**: The problem explicitly requires a Python-served desktop web page and a Swift package, with no external services or synchronization. Standard-library facilities keep installation and local operation simple. Both expressions implement the same domain rules and can run common scenario fixtures without coupling their storage.

**Alternatives considered**: A shared network backend or synchronization would contradict the independent-local-data constraint. A web framework or third-party persistence library adds a dependency without a demonstrated need; a mobile UI is explicitly out of scope.

## Local storage and atomic changes

**Decision**: Each expression stores its own versioned JSON document in a local file. Load and validate state, compute a complete proposed mutation in memory, then serialize and atomically replace the file only after all validation and cascading rebookings succeed. Serialize access to a store so concurrent operations cannot overwrite each other; a failed operation leaves the prior state intact. Keep historical snapshots required for invoices.

**Rationale**: A single document fits the stated small synthetic dataset and the requirement that all data is local. Staging the entire change ensures multi-job rescheduling and last-departure invoicing are all-or-nothing. Atomic replacement avoids exposing a partially written document.

**Alternatives considered**: Multiple independent files complicate atomic cascades. A database provides stronger transactional features but is unnecessary for the stated scale; in-place file writes risk partial data on failure.

## Earliest booking and cascades

**Decision**: Search working weekdays in chronological order from the requested day or an explicit later lower bound. On each day consider 08:00 and the ends of existing assignments plus the one-hour separation as candidate starts, clipped to the lower bound; select the first candidate where the full interval fits before or at 17:00 and at least the required number of cleaners have no interval conflict, including the hour buffer on both sides. Resolve ties deterministically by cleaner ID. Refuse durations over nine hours, invalid staffing, or a request with fewer eligible existing cleaners than required. Extensions may end after 17:00. Rebook affected future jobs in deterministic scheduled-start/ID order with their required lower bounds, propagating any displacement until the schedule is valid; stage the complete result before committing.

**Rationale**: Availability can only improve at a prior assignment's end plus the buffer, so considering these boundaries plus the daily start and lower bound finds the earliest continuous-time slot without an arbitrary time grid. Checking both sides prevents inserting a job too close to a later assignment. Deterministic ordering makes results reproducible while respecting the specification's freedom in cleaner choice.

**Alternatives considered**: Fixed 20-minute booking slots would miss valid earlier starts; 20-minute increments apply to extensions only. A fixed search horizon could reject a schedulable job without a requirement to do so. Greedy partial writes would violate atomicity.

## Time and billing precision

**Decision**: Use a single configured business-local time zone for workday boundaries and requested dates, and record actual arrival/departure as unambiguous instants. Calculate elapsed time at integer sub-hour precision, accumulate charges at $45 per cleaner-hour, and round the invoice total once to the nearest cent with an explicit half-up rule. Store monetary values as integer cents. Attribute completed billable elapsed time to the local calendar day on which it was worked, splitting a record at local midnight if necessary; weeks run Monday through Sunday.

**Rationale**: Separating local calendar scheduling from elapsed instants handles day boundaries and clock changes consistently. Integer or exact decimal arithmetic avoids binary floating-point currency errors; rounding once matches the specification. Explicit rounding and attribution rules make the independent implementations agree.

**Alternatives considered**: Floating-point dollars and per-cleaner rounding can change totals. Assuming all work remains within a single day fails for allowed late extensions.

## Historical integrity and validation

**Decision**: Preserve immutable invoice snapshots of client and cleaner identification, individual elapsed times and the total at issuance. Treat deletion as removal from active scheduling while retaining the historical references needed for work and invoices. Enforce arrival-before-departure, assignment membership, job state, full-payment equality, and schedule constraints within the domain layer in both expressions. Present recoverable errors at each interface.

**Rationale**: Snapshots allow later edits or deletion of source records without altering issued invoices, and a shared set of domain-level invariants prevents interface-specific bypasses. Retained history also supports utilization.

**Alternatives considered**: Deriving invoice details from mutable live records can change previously issued invoices. Relying on UI-only validation leaves the Swift interface and direct requests unprotected.
