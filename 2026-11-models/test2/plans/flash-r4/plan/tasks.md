---
description: "Task list for Cleaning Business Scheduling and Billing"
---

# Tasks: Cleaning Business Scheduling and Billing

**Input**: Design documents from `specs/001-cleaning-scheduling-billing/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/desktop-api.md, contracts/mobile-logic.md, quickstart.md

**Tests**: INCLUDED — quickstart.md defines the validation gates (`swift test --disable-sandbox` green, `pytest -q` green) with named golden vectors; contract-test tasks therefore precede implementation in each story phase (test-first: verify the tests fail before implementing).

**Organization**: Tasks are grouped by user story (US1–US6 from spec.md, priority order P1→P2→P3) to enable independent implementation and testing of each story. Rules are deliberately duplicated between `desktop/cleaning/` (Python) and `mobile/Sources/CleaningLogic/` (Swift) per research R5 — the two apps enforce identical rules on their own files and are never connected (FR-018).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1…US6 (from spec.md user stories)
- Exact file paths in every description

## Path Conventions

Two sibling projects at repo root (plan.md Structure Decision):

- `desktop/` — Python web app: `desktop/app.py`, `desktop/static/index.html`, `desktop/cleaning/*.py`, `desktop/tests/*.py`, `desktop/requirements.txt`, data in `desktop/data.json`
- `mobile/` — SwiftPM logic package: `mobile/Package.swift`, `mobile/Sources/CleaningLogic/*.swift`, `mobile/Tests/CleaningLogicTests/*.swift`, caller-supplied data file

## Key shared rules (quote points implementation-time discretion cannot invent)

- Booking rule (spec FR-003/FR-004/FR-005/FR-006, research R3): earliest start on the quarter-hour grid anchored at 8:00 (minute ∈ {0,15,30,45}), on-or-after the requested day, weekdays only, inside 8:00–17:00, where `cleaners_needed` (1–3) distinct cleaners are free; conflict iff "the second starts less than 1 hour after the first ends" (strict `<`); jobs > 8 h split as "as many 8-hour parts as it needs, then the rest", each part booked independently on a later workday, preferring first-part cleaners if free and using other free cleaners otherwise; horizon "up to 90 days past the requested day", else refuse with a message and change nothing. Golden: end 12:00 → next 13:00 (12:45 refused); end 12:10 → next 13:15; Saturday request → Monday 8:00; 10 h → 8 h + 2 h.
- Money (research R2): integer cents; 4500¢/h; `Decimal(minutes) * 4500 / 60` rounded ROUND_HALF_UP per line; total = Σ of rounded lines. Golden: 210 min → 15750¢; 240 min → 18000¢; total 33750¢.
- Timezone (research R1, questions.md Q8): `America/Los_Angeles`, wall-clock rules, DST observed via tz database; constructor default, not a user-facing setting.
- Errors (FR-019, data-model validation rule 4): every failure = AppError message / HTTP 400 (bad input), 404 (unknown id), 409 (rule violation) with `{"error": "..."}`, zero writes, app keeps working.
- Q1/Q9 cascades (questions.md): bumped jobs move as a unit (each part independently re-booked on a later workday, preferring first-part cleaners if free and using other free cleaners otherwise); unplaceable cascade → refuse the whole extension, restore every schedule exactly (all-or-nothing).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding for both apps, per plan.md project structure

- [ ] T001 [P] Create the Python venv at the repo root (`.venv`) and write `desktop/requirements.txt` declaring pytest only (Python 3.14 stdlib otherwise, plan.md Technical Context); install and confirm `.venv/bin/python -m pytest --version` works
- [ ] T002 [P] Create the SwiftPM manifest `mobile/Package.swift`: swift-tools-version 6.1, one library target `CleaningLogic` (Foundation only, path `Sources/CleaningLogic`) + one test target `CleaningLogicTests` (path `Tests/CleaningLogicTests`); no external dependencies; validate with `swift build --disable-sandbox` in `mobile/`
- [ ] T003 [P] Scaffold directories with empty placeholder modules per plan.md project structure: `desktop/cleaning/` (models.py, store.py, scheduling.py, timezone_util.py, invoices.py, utilization.py, errors.py), `desktop/static/`, `desktop/tests/`, `mobile/Sources/CleaningLogic/` and `mobile/Tests/CleaningLogicTests/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entities, stores, time grid, and error plumbing that EVERY user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Both language stacks must finish here before any story phase starts.

- [ ] T004 [P] Implement `desktop/cleaning/errors.py`: `AppError(Exception)` carrying a human-readable `message` and a kind in {bad_input, not_found, rule_violation} mapping to HTTP 400/404/409 (contracts/desktop-api.md error envelope; FR-019)
- [ ] T005 [P] Implement `mobile/Sources/CleaningLogic/AppError.swift`: `struct AppError: Error` with `message: String` and `kind: BadInput | NotFound | RuleViolation` (contracts/mobile-logic.md); every failable operation throws it
- [ ] T006 [P] Implement entities in `desktop/cleaning/models.py` exactly per data-model.md: Cleaner (name/phone/email all "non-empty; as supplied", active bool kept true), Client (name/address/phone "non-empty; as supplied"), Job (client_id, cleaners_needed "1, 2 or 3 (FR-002)", expected_length_hours "> 0; not necessarily whole", requested_day "YYYY-MM-DD", status enum `booked`|`cancelled`, parts, invoice_id int|null), embedded JobPart (part_index 0-based, day, start, end "quarter-hour grid from 8:00 (minute ∈ {0,15,30,45}); ≥ 8:00", assignments), embedded Assignment (cleaner_id, arrive local-str|null "recorded to the minute", depart|null, extended_minutes "≥ 0, multiple of 20 (FR-010)"), Invoice (job_id, issued_at, lines, total_cents "= Σ lines[].amount_cents exactly (R2)", settled bool, payment|null), embedded InvoiceLine (cleaner_id, cleaner_name, minutes_worked, amount_cents "Decimal(minutes)*4500/60 rounded ROUND_HALF_UP (4500¢/h = $45/h)") and embedded Payment ("must == invoice.total_cents exactly; any other amount is refused and never stored (FR-016)"); wall-clock strings `YYYY-MM-DDTHH:MM`; to/from-dict JSON round-trip
- [ ] T007 [P] Mirror entities in `mobile/Sources/CleaningLogic/Models.swift`: same record shapes/field names as T006 serialized identically to JSON (contracts/mobile-logic.md: "Entities and JSON shapes are identical to contracts/desktop-api.md / data-model.md"); Codable structs/enums with exact JSON string raw values
- [ ] T008 [P] Implement the atomic JSON store in `desktop/cleaning/store.py` per research R8 / data-model validation rule 5: file holds `{cleaners, clients, jobs, invoices, counters}`; IDs are "integers … monotonically increasing per entity type per file; deleted IDs are never reused" (data-model.md preamble); every mutation = load → mutate in-memory copy → serialize → write temp file → atomic rename under one process-level lock; corrupt/missing file → fresh empty store, never a crash
- [ ] T009 [P] Mirror the atomic JSON store in `mobile/Sources/CleaningLogic/Store.swift` (research R8): `Data` write to temp file + `FileManager.replaceItem` under a lock; identical file layout to T008; loads caller-supplied `dataFileURL` if it exists (persists across restarts, FR-018)
- [ ] T010 [P] Implement the wall-clock time helpers in `desktop/cleaning/timezone_util.py` per research R1: zone `America/Los_Angeles` (constructor default via `zoneinfo.ZoneInfo`, not user-facing); workday instants 8:00–17:00 Mon–Fri; 36 quarter-hour starts "8:00 + 15k, k=0..35" (research R3); wall-clock↔instant conversion via the tz database; spring-forward nonexistent wall times shift to the next valid quarter hour, fall-back repeated times use the first occurrence
- [ ] T011 [P] Mirror the wall-clock time helpers in `mobile/Sources/CleaningLogic/TimeUtil.swift` (research R1): `TimeZone(identifier: "America/Los_Angeles")!` constructor default, `Calendar`-based quarter-hour grid from 8:00, DST behavior identical to T010's golden cases (spring/fall-back days)
- [ ] T012 [P] Cleanly import `desktop/cleaning/*` from `desktop/tests/` (conftest.py adding the package path) and prove `swift test --disable-sandbox` compiles the empty `CleaningLogic` target — the two test gates of quickstart.md §1–2 run from the repo root

**Checkpoint**: Entities, stores, clocks, and errors exist in BOTH languages; any story can now be built and tested in isolation.

---

## Phase 3: User Story 1 - Book a job conflict-free (Priority: P1) 🎯 MVP

**Goal**: `POST /api/jobs` / `bookJob(...)` place jobs by the booking rule: system picks cleaners and start times, conflict-free, with splits, weekend skipping, and the 90-day refusal.

**Independent Test** (spec.md): with cleaners and clients on file, submit booking requests and verify chosen days/times/cleaners, the quarter-hour grid, the 1-hour spacing, multi-day splits, weekend skipping, and the 90-day refusal — without any other story implemented.

### Tests for User Story 1 (write FIRST, verify they FAIL)

- [ ] T013 [P] [US1] Contract tests for `POST /api/jobs` in `desktop/tests/test_booking_api.py` driving the handler in-process (never curl; research R6/quickstart §2): 201 + fully-booked job for a 2-cleaner Monday request (US1-AC1: "starts at a quarter hour … no earlier than 8:00 that Monday" with "no cleaner holding another job that starts less than 1 hour after this one ends or ends less than 1 hour before this one starts"); 400 on `cleaners_needed ∉ {1,2,3}` and `expected_length_hours ≤ 0`; 404 unknown `client_id`; 409 `{"error": "No slot in 90 days..."}` with zero writes (US1-AC6)
- [ ] T014 [P] [US1] Rule tests for the booking engine in `desktop/tests/test_booking_rule.py`: golden vectors from contracts/mobile-logic.md §Golden — cleaner ending 12:00 → next start 13:00 allowed / 12:45 refused (US1-AC2); cleaner ending 12:10 → earliest 13:15 (US1-AC3); Saturday-requested job starts Monday 8:00 (US1-AC4); 10 h = 8 h + 2 h each independently booked on later workdays, using first-part cleaners if free, other free cleaners otherwise; 8 h fits one day 8:00–16:00 (US1-AC5); 90-day horizon exhaustion refuses with message and "no job or assignment is created"; deterministic cleaner choice "in ascending id order among free candidates" (research R3)

### Implementation for User Story 1

- [ ] T015 [US1] Implement the booking rule in `desktop/cleaning/scheduling.py` per research R3: day-by-day scan from requested day ≤ 90 calendar days (weekends skipped), 36 quarter-hour starts per workday (T010 grid), free-check "conflict iff `start2 < end1 + 60min` for the earlier-and-later pair (strict `<`)", pick "the required number N (1–3) of distinct cleaners … in ascending id order among free candidates"; multi-day split "ceil(hours/8) parts of (8, 8, …, remainder), each independently booked on a later workday, preferring first-part cleaners if free and using other free cleaners otherwise"; no slot for any part → `raise AppError` (rule_violation), zero writes (FR-006)
- [ ] T016 [US1] Implement job booking service functions service functions (book/list/read) in `desktop/cleaning/scheduling.py` atop the T008 store (no store.py edit): `book_job(client_id, cleaners_needed, expected_length_hours, requested_day)` validating "dangling id → AppError, no crash" and enum values; list filterable `?from=&to=&client_id=` per contracts/desktop-api.md §Jobs (data-model validation rule 4)
- [ ] T017 [US1] Add the cleaners/client CRUD + jobs HTTP endpoints (`POST/GET/PUT/DELETE /api/cleaners`, `/api/clients`, `POST/GET /api/jobs`, `GET /api/jobs/{id}` with parts+assignments embedded) and the error envelope mapping AppError kind → 400/404/409 `{"error": msg}` in `desktop/app.py` per contracts/desktop-api.md (DELETE behaviors land fully in Phase 7; here create/read/update + unknown-id 404s)
- [ ] T018 [US1] [P] Implement `bookJob(clientId:cleanersNeeded:expectedLengthHours:requestedDay:)` in `mobile/Sources/CleaningLogic/Scheduling.swift` mirroring T015 algorithm-for-algorithm (research R5 "structural mirrors"): 36 quarter-hour starts, strict `<` 1-hour spacing, 8-hour splits "8+8+rest, each independently booked on a later workday, preferring first-part cleaners if free, otherwise other free cleaners", 90-day horizon, `throw AppError(kind: .ruleViolation, message: "no slot ...")` with zero writes (contracts/mobile-logic.md)
- [ ] T019 [US1] [P] Implement cleaner/client CRUD + `readJob`/`listJobs(from:to:clientId:)` in `mobile/Sources/CleaningLogic/` (Scheduling.swift + a `Crud.swift` if needed — same rules as desktop, both apps "enforce everything", contracts/mobile-logic.md §CRUD): create/read/list/update, `throws NotFound` on unknown ids; deletion cascades land fully in Phase 7
- [ ] T020 [US1] [P] Add mobile rule tests in `mobile/Tests/CleaningLogicTests/SchedulingTests.swift` reproducing the exact same acceptance golden vectors as the Python suite (T014) — parity anchor (research R5, quickstart §1): grid, spacing 12:00→13:00/12:45-no/12:10→13:15, Saturday→Monday 8:00, 10 h = 8+2 on independently booked later workdays with first-part cleaners if free, otherwise other free cleaners, 90-day refusal with nothing created, and `bookJob` unknown-client throws NotFound
- [ ] T021 [US1] [P] Wire the booking form into the back office page `desktop/static/index.html` (vanilla JS, same-origin fetch under `/api`): the US1 flow — pick a client, cleaners_needed 1–3, expected length, requested day → 201 shows the system-chosen cleaners, part days and quarter-hour times — "without performing scheduling math themselves, in one interaction" (SC-006), in-page error messages only (FR-019)

**Checkpoint**: US1 fully functional in BOTH apps: bookings are conflict-free and match every golden acceptance scenario; `pytest desktop/tests/test_booking_*.py` and `swift test --disable-sandbox` green.

---

## Phase 4: User Story 2 - Record time in the field with Arrive/Depart taps (Priority: P1)

**Goal**: A cleaner sees their day and taps Arrive/Depart; time worked = depart − arrive to the minute (FR-008/FR-009).

**Independent Test** (spec.md): book jobs, tap Arrive/Depart, and verify each cleaner's recorded time equals tap-to-tap duration to the minute — testable without invoicing.

### Tests for User Story 2 (write FIRST, verify they FAIL)

- [ ] T022 [P] [US2] Tap tests in `desktop/tests/test_taps.py`: `GET /api/day?cleaner_id=&on=` returns the cleaner's parts "with times, client, co-workers" (US2-AC1); `POST /api/assignments/tap` arrive-8:00 + depart-11:30 → recorded time "3 hours 30 minutes" (US2-AC2, 210 min); depart records "to the minute and the job stops accruing time for them" (US2-AC3); Q5 refusals 409 with no change — second arrive ("first tap wins"), depart without arrive, depart < arrive (questions.md Q5, data-model State transitions); arrive-out-of-order allowed (Q3)
- [ ] T023 [P] [US2] Mobile tests in `mobile/Tests/CleaningLogicTests/TapTests.swift`: `daySchedule(cleanerId:on:)` shows jobs with times/client/co-workers; `arrive`/`depart` to the minute → 210 min for 8:00→11:30; second arrive and depart-without-arrive `throw AppError` RuleViolation with the schedule unchanged (contracts/mobile-logic.md §field operations)

### Implementation for User Story 2

- [ ] T024 [US2] Implement tap recording in `desktop/cleaning/taps.py` per data-model §State transitions (taps live on the per-part Assignment): arrive sets `arrive` (local `YYYY-MM-DDTHH:MM`, "recorded to the minute", FR-008) on that cleaner's Assignment on a booked part "they are assigned to"; depart "requires prior arrive for this cleaner on this job (Q5)", `depart >= arrive`, refuses a second arrive — "first tap wins" (questions.md Q5); state machine `(null,null) → (t1,null) → (t1,t2)`, "depart ends accrual"; illegal transitions → AppError rule_violation, no change; expose `day_schedule(cleaner_id, on)`
- [ ] T025 [US2] [P] Implement time-worked derivation in `desktop/cleaning/models.py`: "Time worked (per cleaner per job) = Σ over parts of (depart − arrive) in whole minutes (FR-009)" using zone-aware instants (T010) so DST-affected tap pairs use "real elapsed local time" (spec Assumptions)
- [ ] T026 [US2] [P] Add the tap/day endpoints `GET /api/day` and `POST /api/assignments/tap` (arrive/depart kinds; 409 Q5 refusals returning updated-job-or-error per contracts/desktop-api.md §Taps) in `desktop/app.py`, plus a day view with Arrive/Depart buttons rendering in-page error messages in `desktop/static/index.html` (the desktop app exercises the same field rules on its own file — FR-018, research R5)
- [ ] T027 [US2] [P] Implement `daySchedule(cleanerId:on:)`, `arrive(jobId:cleanerId:at:)`, `depart(jobId:cleanerId:at:)` in `mobile/Sources/CleaningLogic/Scheduling.swift` mirroring T024/T025 (SwiftPM, Foundation only, no UI — FR-018): taps stored as local wall-clock minute strings; `depart` returns `JobWithInvoice?` (invoice part wired in Phase 5); illegal tap transitions throw AppError with zero writes

**Checkpoint**: US1 + US2 both work independently; tap-to-tap minutes are the single source of worked time in both apps.

---

## Phase 5: User Story 3 - Invoice on completion, settle in full (Priority: P2)

**Goal**: Last Depart issues the invoice ($45/h per cleaner line, half-cent-up, total = Σ lines); settlement is one exact payment; issued invoices are immutable (FR-013–FR-016).

**Independent Test** (spec.md): complete jobs with known tap times and verify invoice contents, rounding ($157.50 for 3 hours 30 minutes), totals, refusal of partial payments, and settled/unsettled status — independently of booking choices.

### Tests for User Story 3 (write FIRST, verify they FAIL)

- [ ] T028 [P] [US3] Invoice tests in `desktop/tests/test_invoices.py`: last-depart issues in the same response (FR-014) — US3-AC1: cleaner A 3:30 + cleaner B 4:00 → lines 15750¢ and 18000¢, total 33750¢, each line listing "cleaner name, minutes, amount_cents"; half-cent-up spot check (R2 ROUND_HALF_UP); `POST /api/invoices/{id}/payment` 33700¢ → 409 "payment must equal total ..." and invoice stays unsettled (US3-AC2); 33750¢ → settled with embedded payment (US3-AC3); unknown invoice 404; `GET /api/invoices?settled=|unsettled=` visibility (FR-016)
- [ ] T029 [P] [US3] Mobile tests in `mobile/Tests/CleaningLogicTests/InvoiceTests.swift`: golden vectors "3 h 30 min tap pair → line 15750¢ ($157.50); 4 h → 18000¢; total 33750¢"; `recordPayment(invoiceId:amountCents:)` "Payment $337.00 on a 33750¢ invoice → throw, unsettled; 33750 → settled"; `listInvoices(settled:)` and `readInvoice` (contracts/mobile-logic.md)

### Implementation for User Story 3

- [ ] T030 [US3] Implement invoices in `desktop/cleaning/invoices.py` per research R2: per-line `Decimal(minutes) * 4500 / 60` quantized to integer cents ROUND_HALF_UP; `total_cents = sum(lines)` ("never rounded from the raw sum"); invoice snapshots cleaner name/time/amount ("invoices snapshot cleaner name/time/amount so referenced-record deletion can't alter them", data-model §Invoice); `record_payment` accepts only `amount_cents == total_cents` else AppError rule_violation; no update/delete code path touches an issued invoice (FR-013)
- [ ] T031 [US3] Wire completion→invoice issuance: in the tap path (T024/T026), "mark a job complete when its last assigned cleaner taps Depart, and … issue its invoice at that moment" (FR-014) — complete = "every assignment on every part has a depart tap" (data-model §Job); set `job.invoice_id`; add endpoints `GET /api/invoices[?settled=]`, `GET /api/invoices/{id}`, `POST /api/invoices/{id}/payment` in `desktop/app.py`; render invoices + record-payment entry with in-page error message in `desktop/static/index.html`
- [ ] T032 [US3] [P] Implement `Invoices.swift` in `mobile/Sources/CleaningLogic/` mirroring T030: Foundation `Decimal(minutes) * 4500 / 60` rounded half-up to cents, total = Σ lines; snapshot lines (cleaner_id, cleaner_name, minutes_worked, amount_cents); `depart(...)` returns the freshly issued invoice "when the LAST assigned cleaner departs" (FR-014, contracts/mobile-logic.md); `recordPayment` throws RuleViolation for any amount ≠ totalCents; `listInvoices(settled:)`/`readInvoice` only — "no update/delete surface exists (FR-013)"

**Checkpoint**: US1–US3 functional; completed jobs invoice instantly with exact $45/h half-cent-up math and exact-payment settlement in both apps.

---

## Phase 6: User Story 4 - Ask for more time on a job in progress (Priority: P2)

**Goal**: Arrived, not-yet-departed cleaners take unlimited 20-minute steps extending their end (past 17:00 allowed), with cascade re-bookings of later jobs per the booking rule, all-or-nothing (FR-010/FR-011, Q1/Q9).

**Independent Test** (spec.md): arrive on a job, add 20-minute steps, and verify the cleaner's schedule extends, later jobs cascade-rebook per the booking rule with the ≥1-hour floor, and nothing ever overlaps — testable without invoicing.

### Tests for User Story 4 (write FIRST, verify they FAIL)

- [ ] T033 [P] [US4] Cascade tests in `desktop/tests/test_cascades.py`: US4-AC1 — cleaner arrived on a job ending 12:00 with a later job at 13:15 takes "three 20-minute steps (new end 13:00)" → later job "re-booked by the booking rule starting no earlier than 14:00"; US4-AC2 — steps pushing work to 18:20 accepted though 17:00 passed; US4-AC3 — a bumped job is re-booked the same way and "every cleaner's schedule remains overlap- and double-free"; Q1 moved-as-a-unit (bumped job's parts each independently booked on later workdays with first-part cleaners preferred if free, other free cleaners otherwise); Q9 — unplaceable cascade → 409 with "every schedule restored exactly as it was"; refusals: extend before arrive / after depart (Q5); steps accepted "only while arrived & not departed"; `extended_minutes` "≥ 0, multiple of 20"
- [ ] T034 [P] [US4] Mobile cascade tests in `mobile/Tests/CleaningLogicTests/CascadeTests.swift`: golden vector "Three 20-min steps from a 12:00 end (new end 13:00) re-book the 13:15 later job to ≥ 14:00 by the booking rule (US4-AC1)"; `extend` throws RuleViolation "restoring all schedules if a bumped job is unplaceable in horizon (Q9)"; result reports `rebookedJobIds`; past-17:00 acceptance; tap-order refusals on extend (contracts/mobile-logic.md)

### Implementation for User Story 4

- [ ] T035 [US4] Implement the re-book cascade in `desktop/cleaning/scheduling.py` per research R4: after each 20-min step on an arrived, not-departed assignment (`extended_minutes += 20`), any later job of that cleaner "or of the extended part's other assigned cleaners — Q1: bumped jobs move as a unit, respecting each part's assignments" starting `< new_end + 60min` is "un-scheduled and re-booked by the R3 rule with a floor start ≥ new_end + 60min, cascading repeatedly"; each bumped part independently follows the booking rule on a later workday, preferring first-part cleaners if free, other free cleaners otherwise; horizon-exceeded → whole operation fails atomically restoring prior schedules (Q9); "Extended assignments ignore the ≤17:00 bound; booked parts must respect it" (data-model validation rule 1)
- [ ] T036 [US4] Add `POST /api/assignments/extend` in `desktop/app.py` per contracts/desktop-api.md: `{job_id, cleaner_id, minutes: 20, at: local}` → 200 `{job, rebooked_job_ids}`; 409 "atomically, nothing changed" if cascade unplaceable in horizon (Q9); 409 before-arrive/after-depart (Q5); plus an in-page "More time (+20 min)" control showing re-booked jobs and error messages in `desktop/static/index.html`
- [ ] T037 [US4] [P] Mirror the cascade in `mobile/Sources/CleaningLogic/Scheduling.swift`: `extend(jobId:cleanerId:minutes:at:) throws -> ExtensionResult` — "20-min steps, only arrived-and-not-departed, unlimited, may pass 17:00; cascades re-booking of later jobs of every assigned cleaner (Q1: job moves as a unit) floor newEnd+1h, repeat until clean; throws RuleViolation restoring all schedules if a bumped job is unplaceable in horizon (Q9)" (contracts/mobile-logic.md)

**Checkpoint**: US1–US4 functional; extensions extend schedules past 17:00 and cascades never leave an overlap anywhere (SC-002), failing all-or-nothing.

---

## Phase 7: User Story 5 - CRUD for cleaners, clients and jobs; safe removals (Priority: P2)

**Goal**: Full CRUD with the two removal cascades — cleaner deletion re-books their future jobs with any free cleaners; client deletion cancels their future jobs; invoiced jobs are undeletable (FR-001/FR-012/FR-013, Q2).

**Independent Test** (spec.md): exercise every create/read/update/delete and both removal cascades and verify the inventory and schedules stay consistent — independent of invoicing.

### Tests for User Story 5 (write FIRST, verify they FAIL)

- [ ] T038 [P] [US5] CRUD/removal tests in `desktop/tests/test_crud.py`: US5-AC1 — cleaner with two future jobs deleted → "the cleaner is gone and both jobs still exist, re-booked by the booking rule with free cleaners" (response `rebooked_job_ids`); US5-AC2 — client deleted → "the client and the future job are cancelled and the arrived-at job … untouched" (response `cancelled_job_ids`, status `cancelled`); US5-AC3 — nonexistent id on update/delete → 404 "a message explains the record doesn't exist, nothing changes, and the app keeps working"; FR-013/US3-AC4 — delete of a job with `invoice_id` set → 409 "invoice issued", job remains; Q2 — `PUT /api/jobs/{id}` "edit stands as entered; refused 409 if it would leave any assigned cleaner overlapping or <1h-spaced"; future-job definition "one nobody has tapped Arrive on" (edge: a partially-arrived job is NOT future)
- [ ] T039 [P] [US5] Mobile CRUD/removal tests in `mobile/Tests/CleaningLogicTests/`: `deleteCleaner` returns `RebookedJobs` and future jobs survive re-booked; `deleteClient` returns `CancelledJobs`; `deleteJob` "RuleViolation if invoice issued (FR-013)"; `updateJob` "Q2: refused RuleViolation if overlap result, else stands"; NotFound on unknown ids with the app still usable (contracts/mobile-logic.md)

### Implementation for User Story 5

- [ ] T040 [US5] Implement delete cascades in `desktop/cleaning/scheduling.py` per data-model §State transitions: cleaner deletion — for each of their future jobs (no arrive tap anywhere, FR-012) "re-booked by the booking rule with any free cleaners (assignments replaced), then the cleaner record is removed"; client deletion — "their future jobs → `cancelled`; client record removed", arrived-at jobs and their invoices untouched; job deletion refused iff `invoice_id` set (FR-013); each cascade one atomic store write, unplaceable re-booking → refuse all (Q9-style all-or-nothing)
- [ ] T041 [US5] Implement job update + delete endpoints per contracts/desktop-api.md §Jobs in `desktop/app.py`: `PUT /api/jobs/{id}` enforcing Q2 ("no automatic re-booking of an already-booked job. Edits that would leave any assigned cleaner with overlapping or too-close future parts are refused with a message and change nothing; otherwise the edit stands as entered", questions.md Q2); `DELETE /api/jobs/{id}` → 200 `{"ok": true}` / 409 "invoice issued" / 404; finish cleaner/client `DELETE` routes (`{"ok": true, "rebooked_job_ids": [...]}` / `{"ok": true, "cancelled_job_ids": [...]}`) and CRUD panels (create/edit/delete buttons with in-page messages) in `desktop/static/index.html`
- [ ] T042 [US5] [P] Implement `deleteCleaner(id:) -> RebookedJobs`, `deleteClient(id:) -> CancelledJobs`, `updateJob(...) -> Job` (throws on overlap result), `deleteJob(id:)` (throws if invoice issued) in `mobile/Sources/CleaningLogic/Scheduling.swift` mirroring T040/T041 exactly (both apps enforce everything on their own file, FR-018)

**Checkpoint**: US1–US5 functional; every CRUD + removal path is message-and-no-change on error (SC-001/SC-005) and removals never orphan bookings.

---

## Phase 8: User Story 6 - See utilization per cleaner (Priority: P3)

**Goal**: Per cleaner, billable hours worked out of 8 per workday and out of 40 per Mon–Sun week, midnight-spanning work split per calendar day, uncapped (FR-017).

**Independent Test** (spec.md): enter worked time (including overnight spans) and verify daily and weekly totals — testable purely from tap data.

### Tests for User Story 6 (write FIRST, verify they FAIL)

- [ ] T043 [P] [US6] Utilization tests in `desktop/tests/test_utilization.py`: US6-AC1 / SC-007 golden "a cleaner who works 22:00 to 2:00 has 2 hours on each of the two days" (120 + 120 min slices); US6-AC2 — 9 h Monday → `minutes: 540, of: 480` ("overage shown, not capped"); weeks Monday–Sunday anchored (overnight spans split weeks too); response shape `{"days": [{"cleaner_id","date","minutes","of":480}...], "weeks": [{"cleaner_id","week_start","minutes","of":2400}...]}` per contracts/desktop-api.md §Utilization; no-arrive → 0 hours (research R10)
- [ ] T044 [P] [US6] Mobile tests in `mobile/Tests/CleaningLogicTests/UtilizationTests.swift`: `utilization(cleanerId:from:to:)` — "22:00-02:00 → 120/120 (FR-017, SC-007)"; "Utilization: 9 h Monday → 540/480"; per-day /480 and per Mon–Sun week /2400, "uncapped" (contracts/mobile-logic.md)

### Implementation for User Story 6

- [ ] T045 [US6] Implement `desktop/cleaning/utilization.py` per research R10: "sum of overlaps of each worked interval [arrive, depart) with that day" using zone-aware instants (a midnight-crossing [arrive, depart) splits by zone-aware local midnight); day total `/480` min and "Mon–Sun ISO-style week anchored Monday" `/2400` min, "may exceed 8 (FR-017)"; computed from tap data only (billable hours worked = tap-to-tap, "including extensions" per spec Assumptions)
- [ ] T046 [US6] Add `GET /api/utilization?cleaner_id=&from=&to=` in `desktop/app.py` (response per contracts/desktop-api.md §Utilization) and a utilization view (day cells + Mon–Sun week total, uncapped) in `desktop/static/index.html`
- [ ] T047 [US6] [P] Implement `Utilization.swift` in `mobile/Sources/CleaningLogic/` mirroring T045 (research R10) and expose `utilization(cleanerId:from:to:) -> Utilization` on `CleaningApp` (contracts/mobile-logic.md)

**Checkpoint**: All six stories independently functional in both apps.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Whole-app validations and edge sweeps across stories

- [ ] T048 [P] Error-envelope sweep in `desktop/tests/test_error_envelope.py` (SC-005, tests in-process per quickstart §2): every endpoint rejects junk payload, unknown ids and malformed times/dates with 400/404/409 `{"error": msg}`, the data file byte-identical after each failure, and the handler answering the next request normally (FR-019, no stack traces ever)
- [ ] T049 [P] DST tests in `desktop/tests/test_dst.py` and (mirrored) `mobile/Tests/CleaningLogicTests/DstTests.swift` per research R1 and the spec Edge Cases: a part landing on a spring-forward nonexistent wall time "shifts to the next valid quarter hour"; a fall-back repeated time "use[s] the first occurrence"; a clock-change night inside a workday or a multi-day job changes no booked clock time ("a 2-hour job 8:00–10:00 across a spring-forward night occupies the clock span as booked", spec Assumptions)
- [ ] T050 [P] Persistence/restart tests: `desktop/tests/test_persistence.py` (reload a file saved by a previous process instance → same records, monotonic ids "deleted IDs are never reused"; truncated/corrupt JSON → empty store, message, no crash) and a mobile restart test in `mobile/Tests/CleaningLogicTests/` constructing a second `CleaningApp` on the same `dataFileURL` sees the first one's data (quickstart §3 step 8)
- [ ] T051 [P] Simulated-season overlap sweep (SC-002): `desktop/tests/test_season.py` scripts hundreds of bookings (avg 4.14 h, σ 1.75 h — spec Assumptions shape test data only), taps, extensions and deletion cascades across 12 cleaners, asserting after EVERY operation the invariant "0 cleaner schedules ever contain a double booking or an overlap (a job starting less than 1 hour after another ends)" using effective ends incl. `extended_minutes` (data-model validation rule 1)
- [ ] T052 Back-office page end-to-end walk: run `python app.py` on a port from 18080–18089 (background, loopback only) and step through quickstart.md §3's 8 numbered checks (US5 create → US1 booking incl. 10 h split and refusal → US2 taps → US3 invoice/payment/delete-refusal → US4 extend cascade + 22:00–02:00 → US5 removals → US6 utilization → restart persistence), fixing anything the walk exposes in `desktop/static/index.html` / `desktop/app.py`, then stop the server
- [ ] T053 Cross-app parity check (quickstart §4): run both suites (`../.venv/bin/python -m pytest -q` in `desktop/`; `swift test --disable-sandbox` in `mobile/`) and confirm both reproduce every golden vector in contracts/mobile-logic.md §Golden from independently-entered data in their separate files; confirm the two data files were never read by the other app (research R5)
- [ ] T054 Notes: record the sandbox testing note from research R6 (server validated by direct in-process request calls; no HTTP probes) in each test suite's README (as `desktop/tests/README.md`) so future contributors follow the same gates

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001–T003)**: no dependencies — start immediately
- **Foundational (Phase 2, T004–T012)**: after Setup — **BLOCKS all user stories** (entities, stores, clock helper, error type are used by every rule)
- **User Stories (Phases 3–8)**: each depends only on Foundational
  - **US1 (Phase 3)**: no other-story dependency — MVP
  - **US2 (Phase 4)**: needs US1 bookings to have parts to tap (its tests book jobs), but no US2 task blocks another story; T025 extends T006 models only additively
  - **US3 (Phase 5)**: builds on US2 tap plumbing (T031 completes the T024/T026 tap path); read-only invoice views need only US2 data
  - **US4 (Phase 6)**: builds on US1 booking rule (reuses it for cascades) and US2 arrive/depart states (extend precondition); independent of US3
  - **US5 (Phase 7)**: builds on US1 booking rule (re-book cascades on cleaner deletion); job-delete guard needs US3's `invoice_id` to be meaningful, but the refusal path stands on its own
  - **US6 (Phase 8)**: pure derivation from US2 taps; nothing depends on it
- **Polish (Phase 9)**: after every story phase you intend to ship

### Within Each User Story

- Tests (T013–T014, T022–T023, T028–T029, T033–T034, T038–T039, T043–T044) MUST be written and observed to FAIL before implementation
- Models/derivations before services; services before HTTP/Swift endpoints; endpoints before page wiring
- Python and Swift tracks within a story ([P]-paired desktop/mobile tasks) run in parallel; they share only the contract documents, never each other's files — one person may also run the whole mobile track after the whole desktop track

### Parallel Opportunities

- T001/T002/T003 (Setup) in parallel
- Foundational splits cleanly into a Python track (T004, T006, T008, T010, T012) and a Swift track (T005, T007, T009, T011) — never touch the same files
- After Phase 2, stories may proceed in parallel by developer; pair a story with its contract-tests, or in parallel within a story: desktop task ‖ mobile task (T015/T018, T017/T019, T021/T020, T022/T023, T026/T027, T028/T029, T032, T033/T034, T037, T038/T039, T042, T043/T044, T047)
- All Polish tasks T048–T051 are parallel-safe (distinct test files); do not touch the same module twice at once

---

## Parallel Example: User Story 1 + Story 2 (after Foundational)

```text
Wave A (tests first, all [P], expect FAIL):
  T013 `desktop/tests/test_booking_api.py`
  T014 `desktop/tests/test_booking_rule.py`
  T022 `desktop/tests/test_taps.py`
  T023 `mobile/Tests/CleaningLogicTests/TapTests.swift`

Wave B (Python desktop track ‖ Swift mobile track):
  T015 `desktop/cleaning/scheduling.py` (booking rule)   ‖ T018 `mobile/Sources/CleaningLogic/Scheduling.swift` (bookJob)
  T016 booking service (same file as T015, same developer)  ‖ T019 mobile CRUD
  T017 `desktop/app.py` endpoints                            ‖ (mobile has no HTTP layer)
  T024/T025 taps + time-worked                             ‖ T027 mobile daySchedule/arrive/depart
  (T020 mobile booking tests alongside T018; write with the mobile dev)

Wave C (page, single file — one task at a time):
  T021 then T026 booking + tap views in static/index.html
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: T001 → T002/T003
2. Phase 2: both tracks of Phase 2 (Python ‖ Swift) — checkpoint must pass
3. Phase 3: T013/T014 (fail) → T015–T021
4. **STOP and VALIDATE**: `pytest desktop/tests/test_booking_*.py` and `swift test --disable-sandbox` SchedulingTests green: bookings are conflict-free across all acceptance scenarios 1–6 without invoicing, taps or utilization existing
5. Ready for the back office to book with (SC-006)

### Incremental Delivery

1. MVP (US1) → validate independently
2. + US2 (taps, Phase 4) → day view shows and records tap-to-tap minutes
3. + US3 (Phase 5) → invoices at completion + exact payments
4. + US4 (Phase 6) → extensions with clean cascades (SC-002 sweep)
5. + US5 (Phase 7) → safe removals (SC-001/SC-005)
6. + US6 (Phase 8) → utilization (SC-007); then Phase 9 Polish and the quickstart §3 full walk

### Parallel Team Strategy

Desktop developer runs Phases 2→3→4→5→6→7→8→9 desktop tasks; mobile developer runs the mirrored Swift tasks of the same phases, meeting at the two shared gates: the same golden vectors (contracts/mobile-logic.md §Golden) and the parity check (T053).

---

## Notes

- [P] = different files, no incomplete dependencies; never two tasks editing `desktop/app.py`, `static/index.html`, `desktop/cleaning/scheduling.py` or `mobile/Sources/CleaningLogic/Scheduling.swift` at once
- Desktop HTTP is tested by direct in-process app calls — this sandbox cannot reach loopback HTTP ports (research R6, quickstart §2); server runs only in T052, port 18080–18089, then stopped
- pytest runs via the repo `.venv` (`../.venv/bin/python -m pytest -q` from `desktop/`), never the agent kernel's python; `swift test` always carries `--disable-sandbox` (plan.md Testing)
- Run contract tests BEFORE implementing and show them failing first; commit after each task or checkpoint; keep the two apps' files disconnected (FR-018) at every step
- Anything problem.md/spec does not settle while executing a task goes into questions.md with the assumption you made — never a silent decision
