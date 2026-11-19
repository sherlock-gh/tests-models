"""Builds a blind set for the quality review (README, "Run protocol" 5), on Sherlock:
    python3 blind.py <test> [--out DIR]       test: 1 (documents) or 2 (code, both languages)
Every complete run of that test in any round whose workspace is still on Sherlock, under a random
id, with nothing that names its model, round or server: for each run only the files it wrote
(git, from its first commit to HEAD, as committed), and once for the set what every run started
from (test 1's briefs, test 2's specs) and the rubric. The key (id -> round, server, model, run)
stays beside the set, in results/blind/<set>/key.tsv, and goes to the grader only after grading
(fetch.sh key). Prints the set's name. The set leaves Sherlock only for Dr Watson's inbox,
outside the repo (fetch.sh).
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
W = Path.home() / "workspaces" / "tests" / "2026-10-config"
TASKS1 = ["expense-tracker", "habitkit"]
SKIP = {".specify/feature.json"}   # SpecKit's own bookkeeping, not the model's writing
# A workspace path names its run (test1-<model>-r<n>, round2-a/...): a file quoting one gets
# "<repo>" in its place, and any other path into the home folder "<home>"
REDACT = [(re.compile(rb"(?:/Users/[^/\s]+|~)/workspaces/tests/2026-10-config/[^\s)`'\"\]>]*"), b"<repo>"),
          (re.compile(rb"/Users/[^/\s]+/[^\s)`'\"\]>]*"), b"<home>")]

RUBRIC = {
    "1": """# Blind review: test 1, project management

Each folder under `runs/` is one complete run, under a random id: the documents a model wrote,
as committed, for each task. `briefs/` holds what every run started from (the same for all).
Judge each task against the reference, October's specs and milestones, comparing content, not
method. For each task, two things:

1. Each run's document: fit to send after light edits, yes or no. A run completes test 1 only if
   all of its documents are.
2. Every run's version of the task, ranked from most to least helpful (1 = most), with a reason
   for each place. Helpful means useful to the document's reader, not long or polished: it gets
   the substance right, says what the reader needs to decide or act, and leaves nothing they
   would have to redo. The reader is is the developer who builds
   from it: would they build the right thing, in a sensible order, without guessing? Two runs you
   can't tell apart get the same rank.

Read every version of a task before ranking it. Write one line a run and task to `grades.jsonl`:

    {"set": "<set>", "id": "<id>", "task": "<task>", "fit": "yes", "rank": 2, "note": "..."}
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


def tables(test):
    """(round, server, path of the table, workspace prefix): round 1 had no lanes."""
    out = []
    for d in sorted((T / "results").glob("round*")):
        if (d / f"test{test}.tsv").exists():
            out.append((d.name, "a", d / f"test{test}.tsv", W))
        for lane in ("a", "b"):
            p = d / lane / f"test{test}.tsv"
            if p.exists():
                out.append((d.name, lane, p, W / f"{d.name}-{lane}"))
    return out


def complete_runs(test):
    """[(key row, workspace)]: each complete run whose workspace exists, once"""
    runs, seen = [], set()
    for rnd, lane, path, prefix in tables(test):
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
        sys.exit("usage: python3 blind.py <1|2> [--out DIR]")
    test = args[0]
    base = Path(args[args.index("--out") + 1]) if "--out" in args else T / "results" / "blind"
    name = f"test{test}-{time.strftime('%Y%m%d-%H%M')}"
    top = base / name
    if top.exists():
        sys.exit(f"{top} exists already")
    runs = complete_runs(test)
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
            shutil.copy(T / "test1" / "tasks" / t / "brief.md", s / "briefs" / t / "brief.md")
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
