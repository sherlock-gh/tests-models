# tests-models

The owner's model tests for his home lab: which local and cloud models, with which settings, do each kind of work best. The guardrails are in the user-level CLAUDE.md. Here, the goal is the owner getting a local agent system that runs on its own and that he can trust; the subjects are briefs, models (local, Claude, Codex) and hosts. Each test's README says what it answers and how.

## Roles

- **Hermes** on Sherlock does the tests' work; the runners (`<test>/sherlock.sh`, `cloud.sh`) hand it each job. **Adlerbot** (192.168.40.110) is the only model host: the runners switch its model through inferctl (:8090) and nothing else; nobody logs into it.
- **You** (Claude on Sherlock) set tests up, start rounds, watch them and analyse results. You don't do the work the test measures.
- Results stay on Sherlock under `<test>/results/` (not committed); numbers and grades go into the repo, one set a round. Workspaces and usage files are disposable once nothing needs them.

## Running a round

- **It never waits on the owner.** No rule pauses or halts a round for anyone to read something. A model failure is recorded and the run moves on; a fault in the machine is repaired and the milestone resumes; a fault in the test (a check that can't run, a job that never asks the model) stops the round, and you fix it at once.
- **You watch all of it.** While a round runs, `watch.py` (started by `start.sh`, independent of any session) starts Claude unattended with `watch-brief.md` on every failure, timeout, machine failure and lane end. At each wake, read the why file whole and decide whether the model or the test was at fault. If the test was, fix it, void the runs it ended and redo them, without stopping the round. Then re-arm the watch.
- **Ask for approvals before the owner steps away.** Name every one the unattended work will need and get it while he's there.
- **Visible:** each round's live page is up before the round starts, linked from http://192.168.50.100:18100/tests/: one numbered page a round, `/tests/<test>/round<n>/`, and nothing else (no combined pages, no one-off URLs).
- **Time limits** on everything unattended, stated at handoff; reaching one is recorded as a result. Not for attended commands that take seconds.

## What a test decides

- A plan (test 1) is eliminated at its first failed milestone. A build (tests 2 and 3) runs every milestone and is scored by the hidden tests it passes, so models are ranked, not all zeroed. Every surviving model does every run of every test, as runs disagree (a model failing run 1 has passed 2 and 3).
- Completion (a build's score) first, then quality by a blind review of how helpful the work is. Speed only breaks ties; a difference within a model's own run-to-run spread is a tie.
- Drop a model on its failures' reasons, not their count. A zero is diagnosed before it rejects: if the test caused it, fix the test and rerun.
- A test gives a defined problem, as a competent human would hand over. A model stalling on a missing input is a test fault.
- Before a round, every check must pass known-good work and fail known-bad work (`validate.sh`).
- Cloud models run on the owner's Claude and ChatGPT plans, waiting out a 5-hour limit and starting no turn past the weekly-use cap. They take every round's test 1 with the local models; ask the owner before one starts a coding test.
- Refer to cloud models by alias; the real id lives once, in Hermes's `model_aliases`.

## Working with the owner

- Short: state first, then the command, the machine and the account. Explain only when asked or when a decision is his. Name whose password, on which machine, at every prompt.
- When a rule in this repo conflicts with what he asks, say so in the same reply and change it.
- Commit and push every change as it's made (Sherlock's git workflow).
- Hosts' setup (Hermes's config, inferctl, Modelfiles) is recorded in AI-Infra on Dr Watson; a change to a host's setup is the owner's to back up (`bin/backup`).
