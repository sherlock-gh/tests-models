# Research: Cleaning Scheduling and Billing

No NEEDS CLARIFICATION items remained; the platforms are fixed by problem.md. Decisions below settle design choices.

## D1. Platforms and dependencies
- **Decision**: Python standard library only for desktop (`http.server` + static HTML/JS); Swift package using Foundation only for mobile.
- **Rationale**: "No services" and "local web page served by Python" in problem.md; zero dependencies keeps it runnable offline.
- **Alternatives**: Flask/FastAPI (extra dependency, no benefit at this scale); SQLite (heavier than needed for a few thousand records, though viable).

## D2. Storage
- **Decision**: Single JSON file per app, loaded at start, rewritten atomically on each successful operation.
- **Rationale**: problem.md says each app keeps data in a local file; atomic write prevents corruption on crash.
- **Alternatives**: SQLite (rejected: not requested, two codebases to keep in step); append-only log (unneeded).

## D3. Time and money representation
- **Decision**: Schedule times as whole minutes from local midnight on an ISO date; time worked as whole seconds between Arrive and Depart taps; money as integer cents. Charge per cleaner = round-half-up(seconds × 4500 / 3600) cents = (seconds × 5 + 2) // 4.
- **Rationale**: Avoids floating point; identical results in Python and Swift. Reproduces spec example ($180.00 + $187.50 = $367.50).
- **Alternatives**: Decimal/floating hours (rounding drift, language differences).

## D4. Booking algorithm
- **Decision**: For a job (n cleaners, length L minutes, requested day D): move D to the next weekday if weekend; for each weekday from D onward, consider candidate start times (see D5); pick the first start where at least n cleaners are free for [start−60, start+L+60) relative to their existing jobs (equivalently, their jobs end ≤ start−60 and begin ≥ end+60) and the job ends ≤ 17:00; assign the n free cleaners with lowest id (deterministic, "any free cleaner will do"). Search is bounded (e.g., 366 days); if n exceeds the number of cleaners, or nothing is found, refuse with a message.
- **Rationale**: Earliest-slot rule (FR-004) with a deterministic tie-break makes both apps agree and tests reproducible. Bound prevents infinite loops (edge case).
- **Alternatives**: Pick cleaners to minimize gaps (better utilization but not required; "any free cleaners will do").

## D5. Start-time granularity
- **Decision**: Candidate starts are every minute-aligned instant derived from event boundaries: 8:00, and each existing job end + 60 min for any cleaner; this finds the true earliest start without a fixed grid. Extensions (20-minute steps) can produce ends off the hour, so a fixed hourly grid would miss earliest slots.
- **Rationale**: SC-007 demands the genuinely earliest slot; the earliest feasible start is always 8:00 or some cleaner's job end + 60 min.
- **Alternatives**: Fixed 20-minute grid (could miss earlier slots after odd-length jobs); per-minute scan (correct but slower; usable as the test oracle).

## D6. Extension and cascading re-booking
- **Decision**: Extension adds 20 minutes × k to a job's end (refused if job is complete/cancelled or the amount is not a positive multiple of 20). For each assigned cleaner, any later job starting <60 min after the new end is un-booked and re-booked by D4 with an earliest-start floor of the new end + 60 min on that day; repeat for bumped jobs (worklist) until stable. The whole operation is computed on a copy and committed only if every step succeeds (all-or-nothing).
- **Rationale**: Matches FR-011; copy-then-commit satisfies "change nothing on error".
- **Alternatives**: In-place mutation with rollback (more error-prone).

## D7. Deleting a cleaner with future jobs
- **Decision**: "Future" = not started (no Arrive recorded). Remove the cleaner, then re-book each future job in chronological order by D4 with the remaining cleaners. If any cannot be re-booked, refuse the delete as a whole and report which job fails, changing nothing.
- **Rationale**: Edge case requires the outcome be reported rather than silently dropped; all-or-nothing is consistent with FR-020.
- **Alternatives**: Delete anyway and leave jobs flagged unassigned (leaves a gap in the schedule invariants).

## D8. Invoice immutability and client deletion
- **Decision**: Invoices snapshot client name, cleaner names, times and charges at issue time, so later deletion/re-booking cannot change them. Deleting a client marks future jobs cancelled and keeps in-progress/complete jobs and issued invoices.
- **Rationale**: FR-014.

## D9. Keeping the two expressions consistent
- **Decision**: Write the rules once as prose in `contracts/operations.md`, plus language-neutral conformance scenarios (initial state → operation → expected state/error) in `contracts/conformance-scenarios.md`; both test suites implement every scenario.
- **Rationale**: No shared code is possible across Python/Swift; shared scenarios are the cheapest drift guard.
- **Alternatives**: Shared JSON fixture files loaded by both suites (a good later step; start with scenarios documented in-contract).

## D10. Utilization
- **Decision**: Billable hours per cleaner per day = sum of that cleaner's time worked on jobs whose Arrive date is that day; week = Monday–Sunday containing the date. Shown as hours of 8 (day) and 40 (week) with percentage.
- **Rationale**: FR-019; a job's work is attributed to the day of Arrive.
