"""Builds a blind set for the quality review (README, "Run protocol" 5), on Sherlock:
    python3 blind.py <test> [--out DIR] [--rounds round2,round1-sonnet,...]       test: 1 or 2
Every complete run of that test in any round (or those --rounds names) whose workspace is still on Sherlock, under a random
id, with nothing that names its model, round or server: for each run only the files it wrote
(git, from its first commit to HEAD, as committed), and once for the set what every run started
from (test 1's problem statement, test 2's specs) and the rubric. The key (id -> round, server, model, run)
stays beside the set, in results/blind/<set>/key.tsv, and goes to the grader only after grading
Prints the set's name. The grader reads only results/blind/<set>/set/ and writes grades.jsonl there;
only then does it open key.tsv. Never committed (results/ isn't).
"""
import csv
import random
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

T = Path(__file__).resolve().parent
W = Path.home() / "workspaces" / "tests" / "2026-11-models"
TASKS1 = ["cleaning"]
SKIP = {".specify/feature.json"}   # SpecKit's own bookkeeping, not the model's writing
# A workspace path names its run (test1-<model>-r<n>, round2-a/...): a file quoting one gets
# "<repo>" in its place, and any other path into the home folder "<home>"
REDACT = [(re.compile(rb"(?:/Users/[^/\s]+|~)/workspaces/tests/2026-11-models/[^\s)`'\"\]>]*"), b"<repo>"),
          (re.compile(rb"/Users/[^/\s]+/[^\s)`'\"\]>]*"), b"<home>")]

RUBRIC = {
    "1": """# Blind review: test 1, project management

Each folder under `runs/` is one complete run, under a random id: the spec, plan, task list and
estimate a model wrote, as committed, for one task. `briefs/cleaning/problem.md` is the problem
statement every run started from. Judge each run against that statement; there is no reference
plan. Two things:

1. Each run's plan: fit to build from, yes or no. Fit means that apps built as the plan says
   would do their users' work. Answer each line; one "no" makes the plan not fit.
   - F1 The desktop app is a local web page served by Python, and the tasks build the page.
   - F2 The mobile app is a Swift package holding the app's logic, with no user interface.
   - F3 Each app keeps its data in its own local file; the two aren't connected.
   - F4 In the desktop app alone, the back office can create, read, update and delete cleaners,
     clients and jobs; book jobs with the cleaners assigned for it; have an invoice issued when
     a job completes; record its payment and see which invoices are settled; and see utilization.
     These are judged as operations, not screens: one the desktop app offers through its own
     routes counts, whether or not the plan draws a button for it.
   - F5 In the Swift package alone, a cleaner can see their jobs for the day, tap Arrive and
     Depart, and ask for more time, with later jobs booked again.
   - F6 In ordinary use (including jobs over 8 hours), the planned behaviour meets the problem's
     "How success is judged": no double booking or overlap, errors shown with nothing changed,
     every invoice complete and accurate and issued when its job completes.
   - F7 The plan settles what the developer needs to start: language, framework and storage are
     chosen, not left open.
2. Every run, ranked from most to least helpful (1 = most), with a reason for each place.
   Every fit run ranks above every run that isn't fit. Within each group, rank by how useful the
   apps built from it would be to the business, and how little the developer would have to
   redo: how closely its behaviour follows the problem's rules, how often and how much each
   departure would cost (bookings later than possible, valid requests refused, wrong charges),
   and how sensibly the work is ordered. Not by length or polish. Two runs you can't tell apart
   get the same rank. The estimates are for information only and don't affect either judgement.

The problem statement can't settle everything. Each run was told to record in `questions.md`
every decision it made that the statement leaves open, with the answer it assumed, for the owner
to confirm. Filling a gap is expected; what counts is the result. Judge every assumption, and any
departure from a rule the statement gives, by what the built apps would then do: a result that
breaks a line of item 1 makes the plan not fit; one that leaves the apps useful only lowers its
rank. A recorded assumption costs less than the same one made silently, since the owner can
correct it before the build.

Read every version of a task before ranking it. Write one line a run and task to `grades.jsonl`,
with `questions` the run's open questions in a few words each:

    {"set": "<set>", "id": "<id>", "task": "<task>", "fit": "yes", "failed": [], "rank": 2, "note": "...", "questions": ["..."]}

`failed` lists the item-1 lines the plan fails (for example `["F4"]`), empty when fit.
""",
    "2": """# Blind review: test 2, coding

Each folder under `runs/` is one complete run, under a random id: the code a model wrote, as
committed, in Python (the expense tracker) or Swift (HabitKit). `specs/` holds the spec every run
in that language started from. Every run here passed all hidden tests. For each language, rank
every run from best to worst (1 = best), with a reason for each place: how well it follows the
spec, how clear the code is to the next developer, and how well its own tests would catch a
break; not by length. Two runs you can't tell apart get the same rank. Read every run of a
language before ranking it. Write one line a run to `grades.jsonl`:

    {"set": "<set>", "id": "<id>", "rank": 2, "note": "..."}
""",
}


def tables(test, rounds=None):
    """(round, server, path of the table, workspace prefix)"""
    out = []
    for d in sorted((T / "results").glob("round*")):
        if rounds and d.name not in rounds:
            continue
        for lane in ("a", "b"):
            p = d / lane / f"test{test}.tsv"
            if p.exists():
                out.append((d.name, lane, p, W / f"{d.name}-{lane}"))
    return out


def complete_runs(test, rounds=None):
    """[(key row, workspace)]: each complete run whose workspace exists, once"""
    runs, seen = [], set()
    for rnd, lane, path, prefix in tables(test, rounds):
        rows = list(csv.reader(path.open(), delimiter="\t"))[1:]
        for r in rows:
            if test == "1" and len(r) >= 3 and r[2] == "complete":
                name, lang, run = r[0], "", r[1]
                ws = prefix / f"test1-{name}-r{run}"
            elif test == "2" and len(r) >= 4 and r[3] == "complete":
                name, lang, run = r[0], r[1], r[2]
                ws = prefix / f"test2-{name}-{lang}-r{run}"
            else:
                continue
            if ws in seen or not ws.is_dir():
                continue
            seen.add(ws)
            runs.append(({"round": rnd, "server": lane, "config": name, "language": lang, "run": run,
                          "workspace": str(ws.relative_to(Path.home()))}, ws))
    return runs


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def written(repo, dest):
    """Copies the files the model wrote in this repo, as committed at HEAD; returns how many"""
    root = git(repo, "rev-list", "--max-parents=0", "HEAD").split()[0]
    names = [n for n in git(repo, "diff", "--name-only", "--diff-filter=AM", root, "HEAD").splitlines() if n not in SKIP]
    for n in names:
        out = dest / n
        out.parent.mkdir(parents=True, exist_ok=True)
        data = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{n}"], capture_output=True, check=True).stdout
        for pat, sub in REDACT:
            data = pat.sub(sub, data)
        out.write_bytes(data)
    return len(names)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("1", "2"):
        sys.exit("usage: python3 blind.py <1|2> [--out DIR] [--rounds r1,r2,...]")
    test = args[0]
    base = Path(args[args.index("--out") + 1]) if "--out" in args else T / "results" / "blind"
    name = f"test{test}-{time.strftime('%Y%m%d-%H%M')}"
    top = base / name
    if top.exists():
        sys.exit(f"{top} exists already")
    rounds = args[args.index("--rounds") + 1].split(",") if "--rounds" in args else None
    runs = complete_runs(test, rounds)
    if not runs:
        sys.exit(f"no complete test {test} run has its workspace on Sherlock")
    random.SystemRandom().shuffle(runs)
    s = top / "set"
    (s / "runs").mkdir(parents=True)
    key = []
    for row, ws in runs:
        bid = secrets.token_hex(3)
        d = s / "runs" / bid
        if test == "1":
            n = sum(written(ws / t, d / t) for t in TASKS1 if (ws / t / ".git").is_dir())
        else:
            n = written(ws / "app", d)
            (d / "LANGUAGE").write_text(row["language"] + "\n")
        key.append({"id": bid, **row, "files": n})
    if test == "1":
        for t in TASKS1:
            (s / "briefs" / t).mkdir(parents=True)
            shutil.copy(T / "test1" / "problem.md", s / "briefs" / t / "problem.md")
    else:
        for lang in ("python", "swift"):
            (s / "specs" / lang).mkdir(parents=True)
            shutil.copy(T / "test2" / lang / "SPEC.md", s / "specs" / lang / "SPEC.md")
    (s / "RUBRIC.md").write_text(RUBRIC[test].replace("<set>", name))
    with (top / "key.tsv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(key[0]), delimiter="\t")
        w.writeheader()
        w.writerows(sorted(key, key=lambda k: k["id"]))
    print(name)
    print(f"{len(key)} runs", file=sys.stderr)


if __name__ == "__main__":
    main()
