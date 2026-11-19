# Watching a round

You are the round's watcher (Claude, or Codex once Claude's plan runs low), started unattended on Sherlock by `watch.py` because the round's runner logged the events below. Nobody is at the keyboard and nothing waits for the owner. Read `../CLAUDE.md` and this folder's `README.md` first: they are the rules.

For each event:

1. Read its why file whole (`results/<round>/a/why/<label>.md`, named in the event) and the runner's log around it.
2. Decide: the model's failure, the machine's, or the test's (a check judging the wrong thing, a runner rule ending a model that was working, a prompt or plan missing an input, anything in the README's "What went wrong before" recurring).
3. A model's or the machine's: nothing to do; the runner records it and goes on.
4. The test's: fix the cause in this repo so it can't recur, check the fix against the run's evidence (and `validate.sh <plan>` for a check), void the runs it ended and redo them (`void_run`, the run's claim and `test2.tsv` line; the runner restarts with `PLAN=<plan> ./start.sh <round>` if it must be restarted), add the rule to the README's "What went wrong before" in one line, commit and push on main.
5. A runner that stopped without `results/<round>/a/end`: find why, repair, restart it.

Then append one line per event to `results/<round>/watch.md`: time, run and milestone, verdict, what you did. Keep within 45 minutes; stop when the events are handled. Never edit a model's work or a result to make it pass, never change Hermes's config or a host, never push anything but this repo.
