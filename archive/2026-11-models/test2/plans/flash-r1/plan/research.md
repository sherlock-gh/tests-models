# Phase 0 Research: Cleaning Scheduling and Billing

**Date**: 2026-11-11 | **Plan**: [plan.md](./plan.md)

All unknowns in the plan's Technical Context were resolved below; no [NEEDS CLARIFICATION] markers remain. Web research was not performed in this run — offline environment constraint; each decision cites the spec's own rules and standard-library practice, and each is verifiable by the tests named in quickstart.md.

## D-1: Dual expressions without a shared runtime

- **Decision**: Two independent implementations — Python (`webapp/`) and Swift (`CleanerApp/`) — both written against one language-neutral rule statement kept at `shared/rule-spec.md`. Parallel test suites check both against the same scenario table transcribed from the spec's acceptance scenarios and edge cases.
- **Rationale**: The problem statement's known limits mandate two expressions of one solution ("a local web page served by Python" and "a Swift package holding the app's logic, with no user interface"), each with its own local data file, "not connected". "In sync" is defined there as consistent rules and records, not live exchange (spec Assumptions). A shared runtime (e.g. Python core + Swift FFI) would connect them and add a build dependency nobody asked for.
- **Alternatives considered**: (a) single Python core with a Swift shim via PySwift/C-API — rejected: violates "not connected", huge complexity for zero spec value; (b) duplicate the rules informally in each package — rejected: rule drift is exactly the pain the project exists to fix; the shared rule file is the cheap guard.

## D-2: Web framework / server choice

- **Decision**: Flask for `webapp/app.py`, with a stdlib `wsgiref.simple_server` fallback so the app runs with no third-party install if needed; templates rendered with Jinja2 (Flask's built-in).
- **Rationale**: The back office needs form posts, redirects, and simple page rendering; Flask is the smallest mainstream choice. The fallback matters because the environment may lack network installs (a project dependency, per the working rules, installed in a repo-local `.venv`).
- **Alternatives considered**: FastAPI+uvicorn — rejected: needs async stack and more deps for a synchronous page app; Pure stdlib `http.server` — kept only as the fallback, rejected as primary because hand-rolling routing/forms adds ~200 LOC of plumbing.

## D-3: Booking algorithm (earliest feasible slot)

- **Decision**: Deterministic scan. Candidate days = workdays (Mon–Fri) on or after the requested day, up to a 52-workday horizon. On each day, candidate start times = every minute-grid time from 8:00, stepping by the job's own minute granularity, while start + length ≤ 17:00. A cleaner is free for [start, end] iff they hold no scheduled job where the new job starts less than 60 minutes after that job ends **and** no job where the existing job starts less than 60 minutes after the new one ends (both directions — FR-005 is symmetric spacing). First candidate with ≥ required distinct free cleaners wins; assign the lowest-id free cleaners (cleaners interchangeable).
- **Rationale**: "Earliest slot … where enough cleaners are free" is a search over a finite, tiny space (12 cleaners, ≤ ~200 candidate starts/day); brute force is obviously correct and auditable. Choosing the earliest-possible start on the earliest-possible day yields exactly the "earliest feasible slot" criterion (SC-004). The 9-hour refusal (> one workday) happens before any search, so nothing changes on refusal.
- **Alternatives considered**: (a) constraint solver (OR-Tools) — rejected: external service-sized dependency for a 12-cleaner problem; (b) interval trees / free-gap merging — rejected: correctness risk with the 1 h spacing counted on both sides saves nothing at this scale.

## D-4: Extension and rebooking cascade

- **Decision**: Extension = cleaner requests +20 min on their job's end (no 17:00 cap for the extending job itself, FR-008). Then a loop: for every later scheduled job on that cleaner's schedule starting < 60 min after the (possibly updated) end of the extended job, take the chain in start order; remove it, then rebook it by the D-3 algorithm with a *minimum start* = max(its current day, day of extended-end + 60 min) and floor time as required (≥ 1 h after the extended end, inside 8:00–17:00, Mon–Fri). Rebooking a job can itself displace later jobs — process each cleaner's schedule as an ordered list and re-apply the placement step to every successor whose spacing is violated, repeating until a full pass finds no violation (terminates: each pass strictly moves a job later, and the search horizon is bounded). If rebooking yields no feasible slot, abort the whole operation, restore the pre-operation schedule, and report the situation (FR-016 / edge case: schedule left consistent).
- **Rationale**: Matches FR-009/FR-010 and edge cases literally; "abort whole operation + restore" satisfies "leaves the schedule consistent" and FR-016's "changes nothing".
- **Alternatives considered**: (a) partial commit of already-rebooked jobs — rejected: leaves an inconsistent half-schedule, violating the edge-case rule; (b) postponing the extended job instead of the later ones — rejected: spec says later jobs are the ones rebooked.

## D-5: Delete-cleaner rebooking and delete-client cancellation

- **Decision**: Deleting a cleaner: for each of their future scheduled jobs (earliest start first), rebook by D-3 with minimum start = the job's current booked day/start; the deleted cleaner is removed from the candidate pool first. If any job finds no feasible slot (too few cleaners remain), abort the deletion, change nothing, and report it (edge case "schedule is left consistent"). Deleting a client: cancel (state `cancelled`) all their future scheduled/in-progress? — no: only future `scheduled` jobs; jobs already complete keep their invoices untouched (FR-010).
- **Rationale**: Invoices "already issued MUST NOT change" (FR-010); cancel ≠ delete, so history and utilization keep records.
- **Alternatives considered**: cascading hard-delete of jobs — rejected: destroys invoice linkage the spec protects.

## D-6: Taps, worked time, and invoice issuance

- **Decision**: Arrive records arrival timestamps on the job for that cleaner (state scheduled → in progress on first arrival); Depart records departure (in progress → departed for that cleaner). Worked time = departure − arrival, minute-granular; equal timestamps → $0.00 line (edge case, allowed). Out-of-order/duplicate/foreign taps → error result, no change (FR-007, FR-016). Invoice issuance: when **all** of the job's assigned cleaners have departed, the job goes `complete` and the invoice is created in the same atomic store write. Line per cleaner = round(worked_hours × 45, 2 cents) (round-half-up on the exact Decimal), total = sum of rounded lines (spec Assumption). Invoice immutable afterwards; payments never mutate lines, only settlement state.
- **Rationale**: FR-011/FR-012 plus the rounding assumption, verbatim. Decimal (not float) because $337.50-class cent-exactness is a success criterion (SC-003).
- **Alternatives considered**: float cents — rejected: binary rounding drift; rounding the total instead of lines — rejected by the Assumption (per-line rounding, total = sum of lines).

## D-7: Settlement

- **Decision**: `record_payment(invoice_id, amount)`: unknown invoice → error; already settled → error, nothing changes; amount ≠ total (exact cent/Decimal equality) → refused with message, invoice stays unsettled; equal → settled with payment amount + date (single full payment, FR-013).
- **Rationale**: Literal FR-013/Front acceptance scenario 2 and edge cases.
- **Alternatives considered**: partial/multiple payments — rejected: out of scope by problem statement ("paid in full in one payment"; payment processing excluded).

## D-8: Utilization report

- **Decision**: For cleaner C and reference day D: day total = Σ worked minutes of C's departures on D ÷ 60 against 8 h (shown as x/8 h); week total = Σ worked minutes in D's calendar week (Mon–Sun containing D) against 40 h. Only departed cleaners' worked times count (billable = actually worked); the frames are targets, not caps (extensions may exceed — Assumption).
- **Rationale**: FR-015 + SC-006 "equal the recorded worked time", literal.
- **Alternatives considered**: booked-hours-based utilization — rejected: "worked" is the spec's word; booked time would diverge after extensions.

## D-9: Persistence and error discipline

- **Decision**: One JSON file per app (`webapp/data/*.json`, Swift package's own local file). Atomic write: serialize → write temp in same dir → `os.replace`. Every operation runs fully in memory on a loaded copy; only a successful, conflict-free operation is persisted — this is how "changes nothing on error" (FR-016) is guaranteed structurally, not by try/except scattered around. Errors surface as user-visible message banners on the page (and as `Result`-returning failures in Swift; Swift has no UI so the error text is the return value).
- **Rationale**: Single-writer local files; simplest store that satisfies SC-007 (records exactly as before on every failed op).
- **Alternatives considered**: SQLite — rejected: the two apps must stay independent with human-inspectable local files; rollback-on-crash is overkill at this scale.

## Resolved unknowns summary

| Technical Context item | Resolution |
|---|---|
| Language/Version | Python 3.11+ / Swift 5.9+ (D-1) |
| Primary Dependencies | Flask + Jinja2 (stdlib fallback); Foundation only (D-2) |
| Storage | Local JSON, atomic rename (D-9) |
| Testing | pytest + XCTest + scripted audit workload (D-1) |
| Target Platform | Local 127.0.0.1 web page; macOS SwiftPM package (D-2) |
| Project Type | Dual local web app + logic-only package (D-1) |
| Performance Goals | N/A at scale; bounded 52-workday scan horizon (D-3) |
| Constraints | No services, unconnected apps, immutable invoices (D-5..D-9) |
| Scale/Scope | 12 cleaners, 2 staff, ~4.14±1.75 h jobs (D-3) |
