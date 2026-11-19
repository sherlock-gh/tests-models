# Questions for the owner

Decisions the specify step (specs/001-cleaning-scheduling-billing/spec.md) made where
problem.md does not settle the matter, recorded for confirmation. Each was answered the
way a careful developer would; no work was blocked on them.

## Q1: When does a job longer than 8 hours start its parts?

**Context**: FR-006 splits a >8-hour job into "as many 8-hour parts as it needs, then the
rest," on consecutive workdays, each part "booked by the booking rule."

**Question**: Do all parts share one start time each workday, or is each part placed at
the earliest slot its cleaners have?

**Assumed answer**: Every part of a split job starts at 8:00 on its workday, on consecutive
workdays. All 12 cleaners work the same 8:00–17:00 window, so "as many 8-hour parts as it
needs, then the rest" only works out as intended if the parts are fixed 8:00–16:00 (and the
final part 8:00–8:00+rest) blocks — the problem's own example (a 10-hour job = "8 hours on
one workday, 2 hours on the next") is consistent with this. A part is bookable only if all
of the job's cleaners are free for it; otherwise the whole job moves to a later day as a
unit, and the same cleaner crew stays on every part.

## Q2: What does "the same cleaners on every part" mean when a cleaner is deleted mid-split?

**Context**: FR-001/FR-011 — deleting a cleaner rebooks their future jobs with any free
cleaners.

**Question**: If one cleaner of a multi-part job's crew is deleted while some parts are
still future, what happens to the remaining parts of that job?

**Assumed answer**: The job's future parts are treated as future jobs and rebooked by the
booking rule with any free cleaners (the "same crew" rule yields to the deletion rule, and
the deleted cleaner is gone from the system). Parts already started are untouched.

## Q3: Can a 20-minute extension push an already-booked later job — and may extensions land a job's end arbitrarily late at night?

**Context**: FR-009/FR-010 — extensions "may run past 17:00" in 20-minute steps, as many as
needed; jobs the extension bumps are rebooked by the booking rule.

**Question**: Is there any cap on how late an extension may run, and may it extend into the
next calendar day?

**Assumed answer**: No cap: "as many as needed" and "may run past 17:00" are literal, so an
extension may cross midnight (this is why the utilization rule needs the 22:00–2:00
midnight-split example). Only the cleaner who tapped Arrive on the job requests more time,
and only future jobs (nobody tapped Arrive) get bumped — an already-arrived job is never
moved.

## Q4: Which date owns the minutes between midnight and 8:00 the next morning for utilization?

**Context**: FR-015 — "work that runs past midnight counts on each day for the part worked
that day" (22:00–2:00 → 2 hours on each of the two days).

**Question**: Are the overnight minutes attributed to the calendar day of the tap-based
local time, and do minutes outside 8:00–17:00 (weekends, outside-hours work from
extensions) still count as billable hours?

**Assumed answer**: Yes on both: minutes are attributed by local clock to the actual
calendar day they were worked, weekend days included for weekly totals (Monday–Sunday), and
utilization counts only tapped time (Arrive→Depart), never booked-but-not-worked time.
Daily utilization is still reported "out of 8" even for weekend/extension work.

## Q5: Who are the users of each app, and is there any authentication or role check?

**Context**: problem.md lists "accounts and sign-in" as out of scope; the apps are a local
web page for back office and a UI-less Swift package for cleaners.

**Question**: With no sign-in, how does each app know whether it is acting as back office
or as a cleaner?

**Assumed answer**: Identity is by app, not by login: the desktop web page exposes the
back-office operations (CRUD, booking, invoice status/settlement, utilization) and the
cleaner package exposes the field operations for a given cleaner (day list, Arrive/Depart,
more time). Any caller of an app may use its operations — accepted because all data is
synthetic and this is a fictitious business.

## Q6: What happens to a cleaner's already-arrived or completed job — and its invoice — when that cleaner is deleted?

**Context**: FR-011 covers future jobs on deletion; nothing is said about jobs the cleaner
already tapped Arrive on or finished.

**Question**: May a cleaner with started/completed jobs be deleted at all, and what becomes
of those jobs and their invoices?

**Assumed answer**: Deletion is allowed. Future jobs are rebooked (Q2); jobs already under
way are kept but the deleted cleaner is removed from them, and the job completes and
invoices on the remaining cleaners' departures, listing only the remaining cleaners' lines;
any already-issued invoice survives unchanged (issued invoices never change).

## Q7: Does the implementation plan add a root `Procfile`? (decided by the plan step)

**Context**: The runtime convention for repos here is a root `Procfile` with one `web:`
line that serves the app on 127.0.0.1:$PORT with data under $DATA, so the demo server can
run the desktop app. problem.md says nothing about deployment files.

**Question**: Should the plan create a root `Procfile` in the implementation plan / tasks phase?

**Assumed answer**: Yes. The plan and the tasks phase create a root `Procfile` whose sole
line is `web: PORT=$PORT CLEANING_DATA="$DATA/data.json" python -m desktop.server`. This is
a packaging/deployment convenience mandated by this environment's demo-server convention,
not a product rule, so it does not conflict with FR-017 ("no rules of your own"). A
clarify attempt was made during the plan step and no owner was available.

## Q8: Which web framework / front-end stack for the desktop app? (decided by the tasks step)

**Context**: problem.md says nothing about frameworks; it only describes what the desktop
web app must do and forbids inventing rules or "separate apps" of our own (FR-017).

**Question**: May the desktop app use Flask/FastAPI/React, or must it stay on the stdlib?

**Assumed answer**: Stdlib only, per plan.md's stack decision: `wsgiref.simple_server`
serving a WSGI app with a single dependency-free vanilla HTML/JS page (research R11). No
third-party dependencies are added to the repo. Tasks T001–T003, T016, T017 and T019
follow this.

## Q9: Do the two duplicated rule engines exchange code or data? (decided by the tasks step)

**Context**: The same rules must behave identically in `desktop/` (Python) and
`CleaningKit/` (Swift), but the apps are separate products with independent data files
(research R8).

**Question**: May shared Python/Swift code, a shared config, or a sync mechanism be built
to keep the two engines aligned?

**Assumed answer**: No. The duplication is deliberate ("the two are not connected", plan.md
Structure Decision). Alignment is enforced only by the identical contract-test goldens
G1–G20 of contracts/rules-core.md pinned in both suites (tasks T012–T013, T020–T021,
T026–T027, T030–T031, T034–T035, T038–T039, T043). Any shared file or sync code would
violate FR-017's "two separate apps" and the two-data-files constraint.

## Q10: Which side owns the shared seed helper and the quickstart verification tasks? (decided by the estimate step)

**Context**: tasks.md T011 ("Implement shared seed helper `seed_demo()` in `desktop/store.py`
and its Swift twin as an extension in `CleaningKit/Tests/CleaningKitTests/`") and T047
("Walk quickstart.md §1 through the live desktop page ... confirming ... scenarios pass in
both apps") each span both apps.

**Question**: For estimating (and any per-app scheduling of work), does each app carry half
of T011, and does the desktop side carry T047 even though it verifies both apps' behavior?

**Assumed answer**: Yes to both. T011 is split: the Python `seed_demo()` is counted under
Desktop's foundational group and the Swift test-target twin under Mobile's. T047 (plus
T043–T044, T046) is counted under Desktop's polish group, since the live page walk and the
desktop suite are where that verification happens; Mobile's polish group carries only
T045. Estimating these tasks against one app rather than double-counting them keeps the
two figures additive.

## Q11: What do "hours" and "tokens" mean in this estimate? (decided by the estimate step)

**Context**: The deliverable asks for "hours of a human developer's work" and "the tokens an
AI coding agent would use". problem.md says nothing about either unit.

**Question**: Are partial days, idle time, or multi-developer parallelism to be modeled, and
does "tokens" mean output only or the full agent bill?

**Assumed answer**: Hours are sequential focused effort by one competent human developer
familiar with the stack — not calendar time; the tasks.md "Parallel Team Strategy"
(3 developers) would cut wall-clock, not person-hours. Tokens are the full agent bill
(input + output, cache reads + writes included) for one agent running the whole task to
green tests, per the convention of published agentic-coding token studies; estimates come
with a variance band because the literature measures up to 30× spread between lucky and
unlucky runs on the same task.
