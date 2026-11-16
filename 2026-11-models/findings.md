# What the model tests have taught us about Hermes and its models

For refining Hermes and how it briefs each model. One entry a finding, with its evidence (run
records on Sherlock under `~/tests-2026-11-models/results/`, grades in `grades/test1.tsv`) and
what was done about it. Iterations are this test's passes: 1 (`round1`), 2 (`round2`), 3 (`round3`).

## Harness and Hermes

| Finding | Evidence | Fix |
|---|---|---|
| A model may end its turn by announcing the next step ("Now writing the specification.") without doing it; Hermes takes that as done. | Flash-Next, iteration 1 runs 2 and 3, both right after Hermes refused a file overwrite. | Hermes's `SOUL.md`: never end a turn by saying what you'll do next. Iteration 2: Flash-Next completed 3 of 3. |
| `agent.coding_instructions` reach a model only in a repo with source files, so not in planning repos. | Hermes `agent/coding_context.py`. | Standing instructions for every model go in `SOUL.md`. |
| The problem statement left decisions open, and the test gave models no way to ask; models that filled a gap (a booking horizon) were then marked down for it. | Codex's cross-iteration review found 10 open decisions; Sol's grading failed plans for a booking horizon. | The owner settled the 10 decisions in `test1/problem.md`; each step records any further gap, with the answer assumed, in `questions.md` for the owner (iteration 3). Asking the owner mid-run is preferred, but not yet built. Iteration 3: graders count recorded gaps as good work; 3 of 12 runs still said nothing was open while making choices silently. |
| Models put documents where they chose, or skipped commits. | Gemma, iteration 1 run 3: `tasks.md` at the repo root; several runs stopped with nothing committed. | Each step's prompt names its output path relative to the repo root and ends in a commit (iteration 3). |
| The two apps were described only at the end of the problem, and several models never applied it. | Qwen3-Coder-Next: FastAPI, Docker, iOS screens or no Swift in all 6 runs; Qwen3.5-122B, Gemma: Python command-line tools. | "What to build", naming both apps, opens the problem statement (iteration 3). Iteration 3: 10 of 12 plans name both apps; 4 still have no task for the desktop web page. |
| Models misread boundaries: an 8-hour job limit for a 9-hour day, 15- or 20-minute booking grids, capped utilization. | Laguna S, Qwen3-Coder-Next, Qwen3.5-122B (8 hours); Qwen3.8-27B 4-bit (grids, caps). | The problem states the rules as numbers and gives boundary examples (iteration 3). Iteration 3: no plan used an 8-hour day, a grid or a cap. |
| The problem says the two apps are not connected but not that each runs the whole workflow on its own data, so plans split it: taps and invoice issue only in the Swift app, settlement only on the desktop, leaving each app unable to finish a job. | Iteration 3: Qwen3.8-27B 4-bit runs 2 and 3, Flash-Next run 2, Terra runs 1 and 3, Gemma run 3. | Open: the owner decides whether `problem.md` says so. |
| The check's placeholder pattern fails ordinary text: `[date picker]`, a form field's label, and `/api/<name>`, a route. | Flash-Next, iteration 3 runs 1 and 3, both ended at tasks by it. | Pattern narrowed (13 Nov); Flash-Next's three runs redone, the old ones voided. |

## Models

| Model | What recurs | How to brief it, or whether to use it |
|---|---|---|
| Laguna XS | Calls a `shell` tool, which Hermes doesn't have (its tool is `terminal`); Hermes gave up on 3 of 6 runs. Finished one plan, a command-line tool. | Dropped (owner, 12 Nov). |
| Devstral Small 2 | 0 of 9 runs completed: stops at the first steps with nothing committed (iterations 1, 2), then writes a spec without the template's sections (iteration 3, all 3). | Not usable for this work as it stands. |
| Qwen3-Coder-Next | Finishes most runs but builds its usual web-backend stack whatever the problem asks; iteration 3: FastAPI with a SwiftUI client, or the Swift package as two tasks. | Name the apps first; check the plan against them. |
| Qwen3.5-122B | Python command-line tool instead of the apps, or neither app planned (iteration 3); template sections left out. | Name the apps first; placeholders checked before commit. |
| Gemma 4 31B | Thin plans; leaves the framework and storage open, and template placeholders (`[FEATURE]`). | Exact paths and settled choices in the brief. |
| Laguna S | 8-hour job limit in iterations 1 and 2, gone with the boundary examples; iteration 3: 3 of 3 finished, none fit: no task builds the desktop web page in any of them. | Name every part each app needs. |
| Qwen3.8-27B 4-bit | Completes reliably; adds convenient constraints (booking grids and caps until iteration 3; then refusing deletions). Iteration 3: none fit; run 1's back office has taps in code but no route or page to them, so it never issues an invoice. | Boundary examples; "no other rules" checked. |
| Flash-Next | Detailed plans when it finishes; stopped after a hiccup in iteration 1 (fixed by `SOUL.md`). Iteration 3, redone: 3 of 3 finished, run 1 fit (taps as desktop routes; split parts fixed at 8:00); run 3 fails only on an invoice test expecting a wrong total; run 2's desktop has no taps. | Commit each step; record assumptions. |
| Sonnet (cloud) | Iteration 3: 3 of 3 finished, runs 1 and 2 fit, run 1 tied with Terra run 2 (of 21); run 2 refuses lengths off the quarter hour, run 3 gives a split job one Arrive and Depart. One run used about 1% of the weekly plan. | Control, not a candidate. |
| Terra (cloud) | Iteration 3: 3 of 3 finished, run 2 fit; runs 1 and 3 leave the desktop without Arrive/Depart. | Control, not a candidate. |
| Qwen3.8-27B 8-bit, Qwen3-Coder 30B | Failed the gate (11.7 tok/s; 11 of 20 tool calls parsed). | Not tested further. |
