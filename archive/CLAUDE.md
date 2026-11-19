# The archived tests (Oct–Nov 2026)

How those rounds were run and decided. They apply only if an archived test is rerun; the new approach is not bound by them.

## Running a round

- **It never waits on the owner.** No rule pauses or halts a round for anyone to read something. A model failure is recorded and the run moves on; a fault in the machine is repaired and the milestone resumes; a fault in the test (a check that can't run, a job that never asks the model) stops the round, and you fix it at once.
- **You watch all of it.** While a round runs, `watch.py` (started by `start.sh`, independent of any session) starts Claude unattended with `watch-brief.md` on every failure, timeout, machine failure and lane end. At each wake, read the why file whole and decide whether the model or the test was at fault. If the test was, fix it, void the runs it ended and redo them, without stopping the round.
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

