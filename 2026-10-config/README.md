# Local LLM Lab: survivor round

Oct 25, 2026

## Purpose

Find local configurations that can complete project-management work and real Python and Swift builds. Each test fails configurations; the pick is made from whoever survives. Earlier versions of this plan are in git history.

**What decides:** completion first (did it deliver the whole piece of work), then quality (is the delivered work good and helpful, not just there). Speed only breaks a tie.

**The pick among survivors:** the one whose work the blind review ranks best, with no preference for the control. One model ranks above another only if its runs' average place beats the other's by more than its own runs' places differ (the larger of the two models' gaps); otherwise they tie, and the faster at the gate wins (owner, 9 Nov).

**Already decided, not retested** (October): documents stay on frontier (October's local leader, Qwen3.8-27B 8-bit, was dropped on 2 Nov at 11.5 tok/s, with faster models in test 1); design, Gemma 4 31B 4-bit.

## Fixed

- **System under test:** local models on Adlerbot plus Hermes on Sherlock, in `hermes-in` (one repo; since 8 Nov a job may install its project's dependencies inside the repo, and nowhere else). No frontier model in the operating path.
- **Test bench:** Opus, from Dr Watson, writes the tasks, hidden tests, reference solutions, rubrics and scripts, and grades blind. The owner starts each test with a command Opus gives.
- **Control:** Qwen3.8-27B 4-bit on MLX-LM, thinking off, Hermes at 64K: production.
- **Settings:** thinking off; each model's published sampling (temperature, top-p, top-k for thinking off, `models.txt`; penalties are applied to no model); Hermes' production settings; context 64K. Until 26 Oct every MLX model ran with Qwen's sampling; the runs of models whose own differs were redone.
- **Ollama:** a model named without a "/" in `models.txt` is an Ollama model on Adlerbot (account adlerbot): run-mlx starts Ollama (`~/ollama/ollama`, listening on 127.0.0.1:11434 only) with `~/scripts-llm/ollama-proxy` in front on :8080, which turns thinking off; with an MLX model served, Ollama isn't running. An Ollama model runs with its model file's sampling, penalties included: Qwen3-Coder 30B's is Qwen's published 0.7/0.8/20 with repeat penalty 1.05. Its context is set in the model file, as Ollama's default is far below 64K: `flash-next` (`~/scripts-llm/flash-next.Modelfile`), and `qwen3-coder-30b-64k`, built 7 Nov from `qwen3-coder:30b` with `PARAMETER num_ctx 65536`. Setup: AI-Infra REBUILD.md step A8 and `hosts/adlerbot/README.md`. A missing Ollama model fails its gate at the load; that zero is diagnosed like any other.
- **Hardware:** Adlerbot, MBP M3 Max 128 GB, 2 TB, GPU limit 120 GB; Sherlock, Intel MBP 16 GB; Dr Watson, M4 24 GB. Adlerbot is dedicated to these tests and they run day and night.
- **Data:** what runs produce stays on Sherlock; only numbers come into the repo. Agents never see the repo, hidden tests or rubrics.

## How every test runs: milestones, and machine failures repaired

Each piece of work is split into milestones. Each milestone is one Hermes job that starts where the previous one left off and must end in a commit; the agent is told to commit when the step is done.

**A model failure ends the run.** The next run starts at once; nothing waits on a run that can't finish. **A machine failure is repaired** and the milestone resumes from its last commit; it never counts against the model.

| What happens | Counted as | What the runner does |
| --- | --- | --- |
| The agent finishes and the milestone's checks pass | Pass | Next milestone |
| The agent finishes and the checks fail | Model failure | Run ends |
| The check itself can't run (its own error, a clone or temp-folder failure, no tests selected) | Fault in the test | Round stops |
| The agent stops without delivering (a reply with no tool call, Hermes' loop guard, Hermes giving up on the model's invalid tool calls) | Model failure | Run ends |
| The milestone's time limit passes while the agent is working | Model failure | Run ends |
| The model server crashes or stops answering | Machine failure | Restarts the server, commits any work in progress, resumes the milestone |
| Hermes crashes (exits nonzero without finishing its turn, or reports the turn failed, other than on invalid tool calls), or hangs (no request to the model and no file change for 5 min while the server is healthy) | Machine failure | Restarts Hermes, commits any work in progress, resumes the milestone |
| A single model request times out | Machine failure | Retries it |

A server outage counts as the machine's even when it comes at the time limit. At most 2 repairs per milestone and 4 per run (a test 1 run's tasks share the 4). Past that, the run is marked machine-failed, isn't counted, and is rerun once at the end of the test. Every repair is logged with its cause.

**Runs:** 3 per configuration, and a configuration survives a test if it completes the whole piece of work in 2 of the 3. The third run is skipped once the first two settle it (both complete, or both fail).

**Rounds:** round 1 ran 25–31 Oct. Its failures were read one by one (2 Nov): about half were the test's, not the models' (a hang watch blind to the second server, a committed build cache failing Swift checks, two hidden tests asserting what the spec doesn't say), and those are fixed. Round 2 judges every model left in contention on every test, with results only from the fixed test; each round keeps its own results and page. A result counts only if it came from the fixed harness on a server it watched correctly.

**Results so far** (`rounds/`; every failure's reason was read):
- **Test 1:** its tasks, runs and results are not in this repository.
- **Swift:** Laguna S survives (2 of 3 in rounds 1 and 2); every other model fails, Flash-Next in rounds 2 and 3. Not rerun.
- **Python:** no survivor in rounds 1 to 4 (round 4 with a review and a send-back), so not tested again. It can be passed through this harness: Flash-Next's round 2 run 2 built the whole app, and `validate.sh` checks it each round.
- **A self-review** (round 4, `rounds/round4/`): the same model reviewing each Python step and getting it back once caught none of its misses and broke one finished step. It is out of the runner, and production's board review is off (owner, 10 Nov).
- **Out of every test:** Qwen3-Coder 30B (the gate, on MLX-LM and on Ollama: it drops the opening `<tool_call>`), Qwen3-Coder-Next, Laguna XS (owner, 7 Nov). Qwen3.5-122B and Devstral fail Python and Swift, without a review.

## Cloud comparison (from 10 Nov): frontier models on the same tests

**Why.** The owner wants frontier models on the tests the local models ran, to compare (10 Nov). It changes no survival result and no pick.

**What runs** (`cloud.sh`, from `start-cloud.sh`): one model from `models.txt`'s cloud lines a round, through Claude Code (a `claude-*` model) or Codex (a `gpt-*` model) on Sherlock, on test 1 and on test 2 in Python and Swift, 3 runs each, the third only when the first two differ, with the local models' prompts, checks, 90-minute milestone limit and repair rules (`lib.sh`, `test1.sh`, `test2.sh`). Each job is one turn on the agent's defaults (its tools and thinking) and Sherlock's `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md` (the git rule, as Hermes's SOUL.md has it), with the agent's own permission prompts or sandbox off inside the fence. `cloud-in` fences it as `hermes-in` fences Hermes, except that the agent reads its own sign-in (`~/.claude`, or `~/.codex`), and this test's folder (the runner, the hidden tests, every result) is closed to it, which `hermes-in` leaves open. A preflight step must pass, and every turn must report the model under test, or nothing is recorded. Each model is a round so that the blind review sets its complete runs beside the local models'. Two cloud rounds may run at once (one Swift build at a time between them); a local round may not run beside either.

**The plans' limits bound it, not 72 h.** The owner's Claude Pro and ChatGPT plans have 5-hour and weekly limits, shared with his own use; each turn reports both (`cloud_turn.py`). Turns start only from 22:00 to 07:00 (`HOURS`). A turn a usage limit cuts off is redone as the same step once the limit resets, neither a repair nor counted in the 90 minutes. No turn starts while the weekly use the last turn reported is at `WEEK_MAX` percent (80) or more; the round waits for the week to reset. Round 6 (Opus 5.5) ran before this, by day: one test 1 run used 127K output tokens and 3.8M input (3.3M of it cached reads), about 25 minutes of work, and took the 5-hour window, already partly used, to its limit; the runner then counted every limited turn as a machine fault and ended with no complete run.

**Not like for like:** the agent differs too (Claude Code or Codex, not Hermes), and so does the setting (the agent's thinking, not off; no 64K cap). A difference measures the model with its agent against a local model with Hermes. No gate: test 0 checks a local server's tool calls and speed.

**Data:** test 1's briefs, and all written from them, go to Anthropic or OpenAI. The workspaces, the turns' streams (`~/.test-usage/<round>-a/`) and the agents' transcripts stay on Sherlock.

**Start** (owner), from this folder: `./start-cloud.sh <name> <round>`, e.g. `./start-cloud.sh sonnet round7`. It refuses while a local round's runner is alive on Sherlock, and doesn't rerun `validate.sh` (round 5 validated these checks). Page: `http://192.168.50.100:18100/test-round/<n>/`.

**Grading:** `./fetch.sh 1` and `2` then hold the cloud models' complete runs among the others'. A Claude model grading them may favour Claude's; a blind review by another model would check that.

## Test 0: gate

**Fails:** models that don't load, don't fit, whose tool calls don't parse, or that generate under 15 tok/s on Adlerbot (owner, 2 Nov; Qwen3.8-27B 8-bit went out at 11.5). About 3 h.

Each model on its engine at 64K: load, one reply, resident memory, no swap (20 min a load); then 20 tool-call prompts, each of which must parse (3 min a call). Speed is recorded for information. Downloads first, each try limited to 4 h: Laguna S 2.1 4-bit (`TensorFold/Laguna-S-2.1-MLX-4bit`, 66 GB; the MLX link below holds kernels, not weights) and Devstral Small 2 24B 4-bit (`mlx-community/Devstral-Small-2-24B-Instruct-2512-4bit`; 2512 is the newest Devstral). A tool call parses when the reply calls one of the offered tools with a JSON object holding that tool's required fields. Models, ids and prompt caches: `models.txt`; the calls: `test0/gate.py`.

## Test 1: project management (runs first)

**Fails:** models that can't carry a plan through the SpecKit steps to a document fit to send. About a day.

- **App plans, tying this test to the coding test:** a SpecKit spec, plan and task list for the expense tracker and for HabitKit, from a one-paragraph brief each, compared with the specs and milestones the coding test builds from.
- **Milestones:** SpecKit's steps in order: spec, plan and tasks. Each is one Hermes job in a repo holding the brief and SpecKit's templates (copied in, not installed). The research step may need the web; whether a run gets it is recorded.
- **Completion:** each step's file has every section its template requires, filled in, with no placeholders left. Checked by script.
- **Quality:** Opus's blind review against the reference (rubric in `blind.py`). Each document is fit to send after light edits, or not; a run completes only if every document is complete and fit to send. Then, for each task, every run's version is ranked by how helpful it is to its reader (the developer who builds from it), with a reason for each place.
- **Models:** every model in `models.txt` that passes test 0 (round 2: the coding models too, to see whether one model can do both jobs).
- **Limits:** 90 min a milestone, a backstop.

## Test 2: coding

**Fails:** models that can't build the whole app, step by step, in Python or in Swift. About a day and a half.

- **The work:** October's two specs, split at their own sections. Python, the expense tracker in 6 milestones: data model and store, command line, monthly report, CSV import, budgets, web interface. Swift, the HabitKit package in 5: Day, schedule and habits, the store, check-ins and streaks, completion rates.
- **Checks:** hidden tests per milestone (`test2/python/milestones.txt`; Swift, one file a milestone in `test2/swift/hidden/`; HabitKit's step 2 has two new tests, as October's reached it only through the store). They are cumulative: each milestone reruns every earlier milestone's tests too, so breaking finished work fails the milestone.
- **Completion:** all milestones pass, which means the whole app is built. Each language is judged on its own, so Python and Swift can have different survivors.
- **Quality, for survivors:** Opus's blind review of the code (rubric in `blind.py`): each language's runs ranked by how well they follow the spec, how clear the code is, and how well their own tests would catch a break.
- **Models:** every model in `models.txt` that passes test 0.
- **Limits:** 90 min a milestone, a backstop.

## Follow-ups

- **Quantization:** the top 2 survivors of each test by quality, at their other available precision (for example Qwen3-Coder-Next 8-bit), with the same tasks and survival rule.
- **Context:** only if a run's log shows Hermes compressing its context. Then the survivors run again at 128K.

## Run protocol

1. Opus prepares the test in the repo: tasks, hidden tests, configurations and the script.
2. The owner starts a round from Dr Watson with one command, `./start.sh [<second server's ssh alias> <its address>]`, and it runs on its own from there; Dr Watson takes no other part. In the foreground (about half an hour) it copies this folder to Sherlock and the servers, finds the models the second server holds with 16 GB of its memory left free (Ollama models stay on Adlerbot; each machine's engine and weights are its own), files the previous round away, and runs `validate.sh`: test 2's checks must pass round 1's complete work and fail its wrong work, on Sherlock, or nothing starts. It deletes no workspace (the blind review reads the complete runs), and starts `adlerbot.sh` on each server and a lane of `sherlock.sh` on Sherlock for each. A second server that holds none of the models gets no lane, and the round runs on Adlerbot alone. Run again during a round, it adds a lane that isn't running and leaves what runs.

   **Lanes.** The two lanes run at once from one queue (`lib.sh`): a unit is a model's gate, its test 1, or its test 2 in one language, and runs wholly on one server. Lane a, on Adlerbot, runs every gate, so speeds are Adlerbot's. Lane b takes a model only after Adlerbot's gate passed it, with twice the milestone backstop (time only breaks ties). A unit whose lane dies is taken over by the other lane and starts over there. One Swift run at a time on Sherlock, across lanes. Hermes's config is production's and never changes during a round: each job names its model (`-m`) and its lane's server (`--provider custom` with `CUSTOM_BASE_URL`), so the lanes can't touch each other. Each lane keeps its results in `results/<round>/<lane>/` and its workspaces in `~/workspaces/tests/2026-10-config/<round>-<lane>/`; each repo's `.git/info/exclude` keeps build output out of git, whoever commits.

   Sherlock holds no keys: a lane asks for a model by requesting `/runner/load/<name>` on its server's :8080, which `adlerbot.sh` reads from the server's log. On Adlerbot it switches the launchd service; elsewhere it runs as that host's user and starts the server itself with the same flags (prompt cache at most 8 GB), whose own model service must be stopped first. Adlerbot records each model's memory and the swap it added (`results/loads.tsv`). A fault in the runner never becomes a model result: a preflight milestone on the production model must pass before a lane records anything, a job that ends without one model call stops the lane, and a check that can't run stops it. A model failing never stops anything. The round's 72 h limit counts from its first start; reached, it ends as incomplete. The round is a Work board run (`~/scaffolding/tests-2026-10-config`): Telegram reports each run's result, a lane stopping and why, and the round ending, dying or stalling for 20 minutes. Every milestone that doesn't pass, and every repair, leaves a why file in its lane's results (`why.py`): the runner's 30-s watch, Hermes's session turn by turn (test 2's commands whole; test 1's only as their program and a fingerprint, as client content), the check's full output and the repo's git state. The status page, http://192.168.50.100:18100/test-round/ (`status.py`, through Sherlock's demo server, so Dr Watson only), lists the rounds, round 1's page as it ended; each round's page shows every model and permutation as a cell, with the server under each score, and each lane's state. Limits are stated at handoff.
3. Runs proceed hands-off; the runner repairs machine failures and moves on after model failures, as above.
4. The script appends each milestone's numbers to its lane's `runs.jsonl`: configuration (engine, model file, quantization, context, thinking, Hermes settings), outcome, repairs and their causes, time and tokens. Outputs stay on Sherlock, in the lane's workspaces, and are deleted once the pick is made.
5. For grading, `./fetch.sh 1` (documents) or `./fetch.sh 2` (code) builds a blind set on Sherlock (`blind.py`) of every complete run whose workspace is still there, and copies it to `/private/tmp/claude-502/lab-inbox/<set>/` on Dr Watson, outside the repo and never committed. A run is under a random id, with only the files it wrote, as committed, and workspace paths in them replaced by `<repo>`; the set holds the briefs or specs once and the rubric (`RUBRIC.md`). Opus grades without seeing configurations and writes `grades.jsonl` in the set's folder; then `./fetch.sh key <set>` brings the key (id to round, server, model, run), which stays on Sherlock until there is a `grades.jsonl`.

Opus reaches Sherlock only through `to-sherlock` (a plain login as `sherlock`, no forwarding) and Adlerbot not at all; nothing on them reaches Dr Watson. `start.sh` and `fetch.sh` need the owner's ssh keys, so the owner starts them from Dr Watson, and everything moves by a pull from Dr Watson.

## Results

Each round's page and tables (`test0.tsv`, `test1.tsv`, `test2.tsv`) are kept in `rounds/<round>/`; the round running now is on the status page.

## Not tested

Documents and design (decided in October), thinking on (to be tried on the winners), harnesses other than Hermes, speculative decoding, vision, sampling settings, and contexts below 64K. Each can be added later if a result calls for it.

Model sources: [Pinggy, 128 GB local models](https://pinggy.io/blog/top_5_local_llm_tools_and_models/), [VDF, local coding models](https://vdf.ai/blog/best-local-llm-for-coding/), [Kilo, open-weight coding models](https://kilo.ai/open-source-models), [aiera, October 2026](https://aiera.blog/best-open-weight-ai-models-october-2026/), [Laguna S 2.1 on MLX](https://huggingface.co/jacklarmer/laguna-s-2.1-mlx-optimized), [Laguna S 2.1 MLX 4-bit weights](https://huggingface.co/TensorFold/Laguna-S-2.1-MLX-4bit).
