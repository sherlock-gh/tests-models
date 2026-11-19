# Lab test

## Results

OVERALL: Failure.  Local LLM reutrned usable data for comparing local llm performance 6 or 274 test runs.

After a month and over a dozen iterations the general pattern has been one of failures and aborted attempts.  The tested Local LLM configuration are nearly incapable for producing project plans for trivial software development, and entirely incapable of executing on any such plans.

Of 274 test runs, only 81 delevered any data, and of these only 6 yielded usable data.  6 or 274 test runs yielded useful data.

| [November](#November-Tests) | [October](#October-Tests) |
| --- | --- |
| [Round 1](https://sherlock-gh.github.io/tests-models/2026-11-models/round1/)<br>[Round 2](https://sherlock-gh.github.io/tests-models/2026-11-models/round2/)<br>[Round 3](https://sherlock-gh.github.io/tests-models/2026-11-models/round3/)<br>[Round 4](https://sherlock-gh.github.io/tests-models/2026-11-models/round4/) | [Round 1](https://sherlock-gh.github.io/tests-models/2026-10-config/round1/)<br>[Round 2](https://sherlock-gh.github.io/tests-models/2026-10-config/round2/)<br>[Round 3](https://sherlock-gh.github.io/tests-models/2026-10-config/round3/)<br>[Round 4](https://sherlock-gh.github.io/tests-models/2026-10-config/round4/) |

[Download files to reproduce this test](https://sherlock-gh.github.io/tests-models/2026-11-models/files/)

## Goal

Identify the optimal models and model configurations for each type of work.

## Conditions

* PM: Cloud Opus
* Lead Architect: Hermes on MBP Inel 16 GB RAM
* Models: MLX-ML and Ollama on MBP m3 128 GB RAM
* Frontier control: Cloud terra and sonnet

This page is also the home page of the results site, [sherlock-gh.github.io/tests-models](https://sherlock-gh.github.io/tests-models/).

## 4 Stage Test

### Test Stage 0: Gate

Can the model meet minimum requirements?

### Test Stage 1: PM

Using SpecKit and some basic prompting from me, each model use create a project proposal and plan. In this cases we need to design and development a schjeudling and billing system for a cleaning company, include desktop for backoffice and mobile for clearners.

All materiels are evaluated and the highest performcing proposal + plan is used to the drive the next 2 test stages.

### Test Stage 2: Python

Develop the backend application to manage appointment scheduleing, resource allocation, and billing.

### Test Stage 3: Swifth

Develop a mobile app to allow cleaners in the field to over ride the scheduled start and start time to reflect reality.

### Test Stage 4: Website

Create a website for a satirical guru -- i already created this, and i just want to see how close the models come in terms of UI design quality.  Our doesn't have to be the same, just smiliar quality.

## November-Tests

[November Tests](2026-11-models/README.md).

### The tests

| Test | What the model does | Passes when |
| --- | --- | --- |
| Gate | Loads and answers on Adlerbot | Loads at 64K context, 20 of 20 tool calls parse, 15 tok/s or faster |
| 1 · Planning | Plans the house-cleaning problem with SpecKit: spec, plan, tasks, estimate | Every document complete, open questions listed in `questions.md`, and the blind review finds the plan fit to build both apps from |
| 2 · Python | Builds the desktop app, a local web page, from the best local plan, one milestone at a time | Every milestone passes its hidden tests, earlier milestones' tests included |
| 3 · Swift | Builds the mobile app's logic, a Swift package with no screens, the same way | Same as Python |
| 4 · Website | Builds a site from the owner's brief and images | The owner judges it against his own site |

### Why this way

- **One problem, written with the owner.** The test measures planning, not guessing what the problem is.
- **Finished first, then quality.** Unfinished or unusable work doesn't help. Speed only breaks ties.
- **Each test drops models.** Time goes to the models that could be chosen.
- **Three runs each.** One run can be luck. A model needs 2 of 3; a gap smaller than a model's own run-to-run spread is a tie.
- **Crashes don't count.** If Hermes or the model server breaks, it is repaired and the work resumes.
- **Graded blind.** Graders don't see model names. Hidden tests check only what the plan says.
- **One plan for all builds.** So builds compare models, not plans. Cloud models also build their own plan.

### Reading the results

| Mark | Meaning |
| --- | --- |
| complete | Finished and usable. |
| failed | Finished but not usable. F-numbers (F1, F2…) name the checklist items it misses. |
| incomplete | Stopped before the end; the cell says where. |
| machine fault | Broke for a reason that isn't the model's; redone. |
| #n of N | Rank among finished runs; #1 is best. |
| 2/3 | Complete runs out of runs done. |
| own / local plan | A cloud model's build cell is split: its own plan above, the local plan below. |
| not needed | A cloud model skips run 3 when runs 1 and 2 agree. |

### Iterations

| Iteration | Dates | What changed |
| --- | --- | --- |
| Iteration 1 | 11 Nov | First pass: the gate, and planning by every local model, Sonnet and Terra. Terra also built its own plan. Flash-Next stopped 2 of 3 runs by saying what it would do next instead of doing it. |
| Iteration 2 | 11–12 Nov | One change: Hermes tells models not to end a turn by announcing the next step. Flash-Next then finished 3 of 3. In the blind review only Terra's plans were fit to build from, and the problem left 10 decisions open. |
| Iteration 3 | 12–13 Nov | The owner settled the 10 open decisions and added rules to the problem; each step names its output file and lists open questions. Laguna XS dropped. Fit plans: Sonnet and Terra, and Flash-Next run 1, the only local one. |

## October Test

[October Tests](2026-10-config/README.md).

### The tests

| Test | What the model did | Passed when |
| --- | --- | --- |
| Gate | Loaded and answered on Adlerbot | Loaded at 64K context, 20 of 20 tool calls parsed, 15 tok/s or faster |
| 1 · Planning | Two proposals, then spec, plan and tasks for two small apps | Every document complete, and the blind review found it fit to send |
| 2 · Python | Built an expense tracker in 6 milestones | Every milestone passed its hidden tests, earlier ones included |
| 3 · Swift | Built a habit-tracking package in 5 milestones | Same as Python |

### Why this way

- **Each test dropped setups.** The pick came from whichever survived.
- **Finished first, then quality.** Speed only broke ties.
- **Production as the reference.** Every model ran with production's settings (thinking off, Hermes at 64K), so a difference is the model's.
- **Three runs each.** A setup needed 2 of 3; run 3 ran only when runs 1 and 2 disagreed.
- **Crashes didn't count.** They were repaired and the work resumed.
- **Hidden checks.** Models never saw the tests or rubrics.

### Reading the results

| Mark | Meaning |
| --- | --- |
| complete | Finished the whole piece of work. |
| failed | The model's own failure: failed a check, stopped, or ran out of time. |
| machine fault | Broke for a reason that isn't the model's; redone. |

### Iterations

| Round | Dates | What changed |
| --- | --- | --- |
| Round 1 | 25–31 Oct | Every setup on every test. About half the failures were the test's own faults (a hang watch that missed the second server, a build cache breaking Swift checks, hidden tests asking for what the spec didn't say). Fixed before round 2. |
| Round 2 | 2–7 Nov | The fixed test, on two servers at once, for every model still in contention. |
| Round 3 | 9 Nov | Only the runs a pick could rest on, on Adlerbot alone. |
| Round 4 | 9–10 Nov | One change: the same model reviewed each Python step and sent it back once. It caught none of its misses and broke a finished step, so the review was removed. No Python run finished. |
| Round 5 | 10 Nov | Flash-Next's third planning run, the last open question. It failed. Outcome: no local model passed planning or Python; Laguna S passed Swift. |
