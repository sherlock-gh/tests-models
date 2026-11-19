# README.md

## Test Goal

We have several different common tasks that we need LLMs to help with.  And we need to identify the best model for each.  

## Direction

We need to test the following 4 cases:

- Project management
  - Take an initial prompt that defines the problem, and the goal
  - leverage SpecKit to plan a project and estimate its effort in human hours and tokens
- Python
  - develop in python the software solution to the problem defined in project management, for desktop
- Swift
  - develop in swift the software solution to the problem defined in project management, for mobile
- Website
  - Unrelated to the previous, create a website for a satirical project already being built, so there is a repo to compare with, and assets.
  
The project plan should drive both the python and swift developments.

## What "best" means

Completion first: did the model deliver the whole piece of work. Then quality: is the work good and helpful to its reader, not just present. Speed only breaks a tie. A model ranks above another only if the gap between them is larger than either model's own run-to-run spread; otherwise they tie. No model is preferred as a control.

## Models

Every local model tested in `2026-10-config`, plus Sonnet and Terra; not Opus or Sol.

- **Local** (on Adlerbot through Hermes): Qwen3.8-27B 4-bit, Qwen3.8-27B 8-bit, Gemma 4 31B, Qwen3.5-122B, Flash-Next, Qwen3-Coder-Next, Laguna S, Qwen3-Coder 30B, Devstral Small 2.
- **Cloud** (through Claude Code or Codex on Sherlock): Sonnet, Terra.

Ids, engines and sampling live once, in this test's `models.txt`. Laguna XS was dropped after test 1's second iteration (owner, 12 Nov): it calls a `shell` tool Hermes doesn't have, and Hermes gave up on 3 of its 6 runs (`findings.md`). Earlier results don't carry over: every model runs every test here.

## Order

1. **Gate** (local models only), the smoke test of everything the tests use with each model, on Adlerbot: inferctl serves it by its `models.txt` name; 20 tool calls parse and it reaches 15 tok/s; it answers a long prompt in full at 128K, else 64K, and that context is set in Hermes and read back through Hermes's own resolver; then one Hermes job, run as every test runs, hands its step to a subagent and commits. A model that fails is dropped from every later test. A fault that isn't the model's (inferctl, Hermes ignoring the context, a subagent that doesn't start, a job that never asks the model, a check that can't run) stops the round before any test result counts (owner, 15 Nov: after the gate, a model can't be unreachable and a script can't hold a wrong reference).
2. **Project management.** Every model plans from the same problem statement.
3. **Build plans** (owner, 11 Nov). Every model, local and cloud, builds from the best-ranked local plan, once round 1's third runs are graded: the test matches local models to jobs, and the cloud models are there for comparison, so every model's result on it is comparable. Each cloud model also builds from its own best plan (Sonnet run 2, Terra run 1), to compare the division of labour: the same model building a local plan or its own. Each plan has its own hidden tests, written from it alone. The owner approves the plan, with what its tests need added to it, before anything is built from it.
4. **Python and Swift** (tests 2 and 3), from the build plans.
5. **Website** (test 4), independent of the others.

The tests are numbered 1 project management, 2 Python, 3 Swift, 4 the website (owner, 16 Nov). The runner's run ids and folders keep their older names: Python and Swift runs are `test2-<model>-python-r<n>` and `test2-<model>-swift-r<n>`, built by `test2.sh` from `test2/plans/`.

## Test 1 · Project management

- **Input:** [`test1/problem.md`](test1/problem.md), the problem statement written with the owner: scheduling and billing for a fictitious house-cleaning business. Defining the problem is the human's job, so the test measures planning, not the model's guess at a problem.
- **Milestones:** each one is a job in a fresh repo holding `problem.md` and SpecKit's templates and skills, and each ends in a commit:
  1. specify (the spec, from `problem.md`)
  2. plan
  3. tasks
  4. estimate: the effort in human hours and in tokens, for each expression, in `estimate.md`

  The prompts, [`test1/prompts.md`](test1/prompts.md), name each skill as a file to read.
- **Completion:** every step's document has every section its template requires, filled in, with no placeholders, `estimate.md` gives both estimates for both expressions, and `questions.md` holds every decision the problem left open with the answer the model assumed, for the owner to confirm (checked by script: committed, maybe empty); and the blind review finds the plan fit to build from, both apps, without guessing at a rule. A plan nothing can be built from is a failed run (owner, 11 Nov).
- **Quality:** the blind review then ranks the plans by how helpful they are to the developer who builds from them.
- **Outcomes:** a run is *complete* (finished, fit, ranked), *failed* (finished but not fit to use, still ranked), or *incomplete* (stopped before finishing: nothing to rank). The same three hold for tests 2 and 3's builds. Machine faults and faults in the test are not model results.
- **Estimates:** for information only; they rank no model. Each plan's token estimate is shown beside the tokens the builds of the fixed plan actually used (`runs.jsonl`): output tokens plus input not read from cache, as a cloud agent reads most of its input from cache.

## Tests 2 and 3 · Python and Swift

- **Input:** the fixed plan (its `spec.md`, `plan.md` and `tasks.md`), the same for every model. The Python build is the desktop expression, a local web page served by Python. The Swift build is the mobile expression, a Swift package with no user interface.
- **Milestones:** Opus groups the fixed plan's tasks into milestones, about 4 for Python and 3 for Swift. Each milestone is one job, told which milestone it is, starting from the last one's commit.
- **Checks:** hidden tests for each milestone, written from the fixed plan alone and run against the interfaces it states. They are cumulative, so breaking finished work fails the milestone's later tests. Where any choice is allowed (which free cleaners get a job), a test accepts any choice the rules allow.
- **Scoring:** a build runs every milestone, whatever the last one's tests said, and work the model left uncommitted is committed for it and checked. Its score is the hidden tests of every milestone that its last milestone's work passes; the page shows each run's and each model's mean, with its range across runs (17 Nov: ending a run at its first failed milestone gave every local model 0, which ranks nothing). **Quality:** blind review of the code against the fixed plan.

## Test 4 · Website

- **Input:** the site repo's `AGENTS.md`, `CONTENT-PRESENTATION.md` and `CONTENT-TOPICS.md`, plus the finished images in `site/assets/`. The owner's `site/` code is withheld and is the reference. No `source-assets/`, and no image generation. The task says the images given are final, because `AGENTS.md` otherwise asks for images made from the withheld kit.
- **Milestones:** Opus splits the work along `CONTENT-PRESENTATION.md`'s sections, one commit each. A milestone passes when its section is in the site and the site loads.
- **Quality:** the owner judges the work, above all whether the satire stays sincere and in the brand's voice.

## Conditions (carried over from `2026-10-config`)

- **Runs:** 3 per model and test; a model survives with complete work in 2 of 3, and 3 of 3 ranks above 2 of 3. Every model runs test 1 three times, as it picks the best plan to build from, not only which models pass (owner, 16 Nov). In a build, local models run all 3, and a cloud model skips the third when the first two agree, as each run uses the owner's plan (owner, 11 Nov).
- **Milestones chain:** each starts from the last one's commit. In test 1 a model failure ends the run, and the next run starts at once; a build goes on to its next milestone (Scoring). A machine failure (server or Hermes crash, hang, request timeout) is repaired and the milestone resumes, at most 2 repairs a milestone and 4 a run. A check that can't run stops the round as a fault in the test.
- **Limits:** a local milestone isn't timed: it ends when the model has changed no file for 2 hours (4 on the second server), a model failure, or at the round's 7-day limit, then 30 minutes to finish the task in hand and commit, which is checked like any other work. In the cloud, 90 minutes of work a milestone. The limits only stop runs that would never end. Every unattended step has a limit, and reaching it is recorded as a result.
- **Local settings:** thinking off, each model's published sampling, Hermes's production settings with subagents (`delegate_task`, one at a time), and each model's context, measured by the gate (a long prompt at 128K, else 64K, answered in full without swapping) and set per model in Hermes's `custom_providers`; 128K at most, though most models hold 256K (measured 14 Nov): a longer thread leaves more room for drift, and re-reading one after a compaction or restart costs 11–46 min at 256K against 6–23 at 128K (owner, 15 Nov).
- **Cloud settings:** the agent's defaults (its own tools and thinking). Turns run in the hours in `cloud-hours` (all day: 00:00–24:00), which the owner may change during a round. A turn cut off by the 5-hour limit waits for the reset and is redone, uncounted. No turn starts once weekly use reaches 80%, so the tests don't use up the owner's plans. This differs from the local setup (another agent, thinking on, its own context), so a cloud result compares a model plus its agent.
- **Runners, all at once.** Sherlock runs every test. The local models' work is done by Hermes, the cloud models' by Claude Code or Codex. Only the models run elsewhere:
  - **Adlerbot (128 GB):** every gate, so speeds come from one host. It also takes any local model's unit from the shared queue, and is the only host for the models it alone can hold (over 48 GB of weights, or on Ollama).
  - **The second server (64 GB):** a gate survivor whose weights leave 16 GB of its memory free, taken from the same queue. Its milestone limit is twice Adlerbot's, as it is slower and time only breaks ties.
  - **Cloud:** Sonnet and Terra, under the plan limits. They take test 1 in every round, in the queue with the local models; before either starts a coding test (2 to 4), the owner approves it, as those use far more of his plans (owner, 16 Nov).

  A unit (one model's runs of one test) runs wholly on one host, so a model's run-to-run spread isn't host noise.
- **Data:** what runs produce stays on Sherlock, and only numbers come into the repo. Agents never see the repo, hidden tests or rubrics. The problem statement is fictitious, and all its data synthetic, so cloud models may read it.
- **Visible:** each round's live status page is up before the round starts. Nothing waits for the owner.

## Grading

Blind sets, built on Sherlock (`python3 blind.py 1|2`): each run under a random id, holding only the files it wrote. Claude grades them from `results/blind/<set>/set/` and writes `grades.jsonl` there before opening the set's `key.tsv`. The website is graded by the owner.

## What went wrong before, and the rule it gives

Every problem recorded in `2026-10-config` and the bake-off, each with the rule that prevents it here. Each rule holds for any task, model or host; a rule is added only for a problem that has happened.

**Inputs**
- **Thin inputs became model failures.** The proposal briefs were one sentence long, and most test 1 failures fell there; one model rightly declined to invent a problem. Rule: every input carries what a competent human would hand over. A model stalling on missing input is a test fault.
- **Prompts sent models the wrong way.** "Follow `<path>`" sent models to Hermes's skill lookup, which found nothing, and they stopped. Rule: a prompt names an instruction file as a file to read in the repo.
- **Tests needed more than the spec said.** Rule: anything a hidden test needs that the fixed plan doesn't state is added to the plan before the owner approves it, so the models see what the tests check.

**Checks**
- **Checks judged the wrong thing.** Hidden tests asserted behaviour the spec never stated, a committed build cache failed Swift checks, the proposal check looked only in the repo root, and the document check passed a `[Your Name]` placeholder and failed a filled-in section. Rule: hidden tests assert only what the fixed plan states, a milestone's hidden tests use only that milestone's and earlier operations (Swift compiles a whole test file: M1's helpers called milestone 2's taps, and every Swift build failed M1), build output stays out of git, each check builds from a clean state, and one milestone's missing piece costs only that milestone's tests (17 Nov: Swift compiled them all as one, and a check read a bare feature folder name as missing). Before any round, every check must pass known-good work (Opus's reference solution, and documents known to be complete) and fail known-bad work (copies broken on purpose) (`validate.sh`).

**Runner and attribution**
- **The harness failed and was blamed on models.** A hang watch was blind to the second server, a fast model restart was missed and recorded as "did not load", and a Hermes exit after the model's invalid tool calls was taken for a crash. Rule: a preflight on the production model must pass before a lane records anything. A job that makes no model call stops the round. Invalid tool calls are the model's failure; a load failure after the gate, or a server outage at the time limit, is the machine's.
- **Runs coached later runs.** Test jobs wrote Hermes's memory (Flash-Next's notes on this very task, from round 3, one of them wrong) and a skill (round 2), which every later job read. Rule: each test job starts from Hermes's memory and skills as they were, and its writes are undone after it (17 Nov).
- **Rules ended models that were working.** 20- and 30-minute milestone limits, and a 10-minute "going in circles" rule, ended jobs mid-work. Then the 90-minute backstop did the same: all 8 jobs it ended were mid-work, every local Python and Swift M1 run among them (15 Nov). Then the 5-minute hang rule ended a model waiting on its own 10-minute test run (17 Nov). Rule: no clock ends a local job the model is still on, a tool it called still running included; only 2 hours (4 on the second server) without a file change, or the round's limit.
- **The test, not the model, was at fault.** Rule: the round never stops for a model's failure (15 Nov: a halt on the production model's first failure stopped round 4 for hours); the session monitoring the round reads each failure's why file as it comes. A model scoring zero is diagnosed before it is dropped. Runs a test fault ended are voided and redone. Read each failure's evidence before naming a cause, and fix the test so the trap can't recur rather than patching runs. Each round keeps its own results, and only results from the fixed harness count.

**Settings and hosts**
- **The context was too small for the work, and Hermes lacked a tool.** At 64K, Hermes compacted Flash-Next's builds every 12 minutes, and it redid finished work; 7 of 7 local builds failed milestone 1. Hermes's subagents, each with its own context, were switched off. Rule: before a round's gate, Hermes has every tool its work needs; the gate measures each model's context, sets it in Hermes, and checks Hermes uses it and starts a subagent.
- **The time limit decided runs.** All six of Flash-Next's builds reached the 90-minute limit while still working, one as it committed, and timed-out work was never checked. Rule: a job at the limit gets 30 minutes to finish the task in hand and commit, and is then checked.
- **Models ran with the wrong settings.** Until 26 Oct every MLX model ran with Qwen's sampling, and Ollama's default context is far below 64K. Rule: each milestone records the sampling and context the server actually used, and a model whose settings differ from `models.txt` has its runs voided.
- **The host was slow, not the model.** Adlerbot on a port that didn't power it ran on battery with the GPU at its minimum clock, an 8x slowdown that took two days to find. MLX also crashed on its GPU buffer limit after hours of serving. Rule: before each round, the owner checks each host is on AC power (inferctl, the runner's only control of the hosts, doesn't report power). The server restarts for each run. Speed, which only breaks ties, is taken from the gate.

**Cloud**
- **Cloud runs burned plan limits.** A daytime cloud round hit the 5-hour limit in about 25 minutes, and every limited turn was counted as a fault. Rule: wait out limits, and cap weekly use.

**Owner and process**
- **The owner couldn't see what ran.** A rule paused the round for his acknowledgement, and he found out a day later. Rule: the live status page is up before the round starts, and nothing waits for the owner.
- **Unbounded steps lost nights.** One build ran over 6 hours. Rule: every unattended step, checks included, has a limit, stated at handoff. A check that can't run, or runs out of time, is the test's fault and stops the round.
- **A self-review made things worse.** In round 4 a model reviewing its own steps caught none of its misses and broke a finished step. Rule: no review or send-back loop in the runner.
- **Rules moved between rounds.** Rule: each round's pass conditions are written here before it runs, and change by one thing at a time between rounds. A test with only one passing model ends its comparison there.

## Rounds

A round is one pass through every test. Within it, local models run on two lanes at once and each cloud model has its own runner.

| Round 1, in order | Models | Tests |
| --- | --- | --- |
| Gate, then test 1 | Every local model; Sonnet, Terra | Gate (local models), test 1 |
| Between | | Blind review of test 1; the owner approves each build plan; its hidden tests and reference solutions; `validate.sh <plan>` passes |
| Tests 2 to 4 | The gate's survivors; Sonnet, Terra (on the best local plan, and on their own) | Python, Swift, website |

Earlier tests' rounds and results don't count here. Round 4 (from 14 Nov) is the first with the gate as the smoke test (each model's context and a subagent through Hermes), subagents and the finish-at-the-limit job: every local model goes through the gate and test 1 (`./start.sh round4`, no PLAN), and Sonnet and Terra take test 1 (`./start-cloud.sh sonnet round4-sonnet`, `./start-cloud.sh terra round4-terra`; owner, 16 Nov: they were left out at its start); the plans are graded blind for the best one, whose hidden tests `validate.sh` passes; then every local model that passed the gate and test 1 (2 of 3 runs complete) builds it in tests 2 and 3, every Python build before any Swift build (`PLAN=<that plan> ./start.sh round4`). The plan is Flash-Next's run 1 (`test2/plans/flash-r4`, the only fit local plan), amended with the owner's split-job rule; its hidden tests and reference were written by Sol through Hermes, not a test subject; no cloud model builds it, as test 2 measures local models (owner, 16 Nov) (owner, 16 Nov: all of test 1 finds the plan; its first start built `flash-i3` after q27-4's test 1 alone, and those builds are voided). Only round 4's results count, not rounds 1 to 3's. The owner ended test 2 on 18 Nov, during Qwen3.8-27B 4-bit's first Python run: after a month of rounds, no local model had finished a build unattended, so local models are out for this work (owner, 18 Nov).

## Starting a round

`test1/problem.md` is approved (owner, 11 Nov). Build plans with their tests: `test2/plans/terra-r1` and `test2/plans/sonnet-r2` (each cloud model's own; the owner approved their interfaces and milestones, 11 Nov). The best local plan's comes once round 1's third test 1 runs are graded; the website task before test 2's local runs.

From this folder, `~/workspaces/projects/tests-models/2026-11-models` on Sherlock:

- **Round 1:** `./start.sh round1` runs the round on Adlerbot. It talks only to Sherlock, whose runner switches Adlerbot's model through inferctl; nobody logs into a model host. A second model host, if there is one, is added as `./start.sh round1 <its inferctl name> <its address> <its memory in GB>`.
- **Its cloud models:** `./start-cloud.sh sonnet round1-sonnet` and `./start-cloud.sh terra round1-terra`. These start with the round's test 1.
- **Tests 2 and 3, the local models:** the same command with the plan they build, `PLAN=flash-r1 ./start.sh round1 ...`. It validates that plan's tests on Sherlock first, once a round (up to an hour), and queues each gate survivor's Python and Swift builds (models.txt's tests column, `2`).
- **Tests 2 and 3, a cloud model on its own plan:** `PARTS="python swift" PLAN=terra-r1 ./start-cloud.sh terra round1-terra-own` (Sonnet: `PLAN=sonnet-r2`, round `round1-sonnet-own`). It validates the plan's tests on Sherlock first, once a round. On the best local plan, the same with that plan's folder and round `round1-<name>-local`.

Each round has its own page, `http://192.168.50.100:18100/tests/2026-11-models/round<n>/`, its local lanes and cloud models together, linked from `/tests/`. Run again, a command adds what isn't running and leaves what is.

**Time limits**

| What | Limit |
| --- | --- |
| `start.sh` in the foreground | 2 min a host's model list; 60 min a validation (only for a new build plan); usually a minute |
| A model's load | 20 min |
| The gate | 70 min the calls (3 min a call); 60 min a long-prompt try, 2 tries; 30 min the Hermes job, then 30 to finish and commit |
| A milestone | until 2 h without a file change on Adlerbot, 4 h on the second server, within the round's 7 days; 90 min of work in the cloud; then, locally, 30 min to finish the task in hand and commit, and the check; past that, a model failure |
| A check | 15 min; then a fault in the test, which stops the lane |
| Repairs | 2 a milestone, 4 a run; past that, the run is redone once at the end |
| A model switch | 20 min (inferctl's own wait is 5 min), then a fault in the machine |
| A local round | 7 days from its first start; each lane resets its host to its default model through inferctl when it ends |
| A cloud round | turns only in `cloud-hours` (00:00–24:00); none while weekly use is at 80% or more; a turn a usage limit cuts off waits for the reset |
