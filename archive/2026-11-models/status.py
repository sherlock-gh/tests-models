"""The status page, on Sherlock: python3 status.py <run folder>
One page a round, local and cloud: ~/demo/www/tests/2026-11-models/round<n>/index.html, which Sherlock's
demo server shows at http://192.168.50.100:18100/tests/2026-11-models/round<n>/ (the lab network), linked
from the tests index (/tests/). Each runner of round n writes its own part (round<n>/part.json, or
part-<cloud model>.json; each why/ file beside it as a page) every 10 s while it runs, and once more as
it ends, then rebuilds the round's page from the round's parts. PAGE_ONLY=1 rebuilds the page alone. One row a model, one cell a permutation (the
gate; test 1 runs, project management; test 2, Python; test 3, Swift; test 4, the website, has no
runner): its result, or what it is doing now. Adlerbot is the only model host, so no cell names it;
a score shows where it came from only for runs carried from an earlier round. The owner reloads it by hand; loaded more than a minute
after it was last written, it says so in red."""
import html
import json
import os
import re
import sys
import time
from pathlib import Path

T = Path(__file__).resolve().parent
ROUND = os.environ.get("ROUND", "round1")
SHARED = T / "results" / ROUND
LOG = Path(sys.argv[1]) / "log.txt"
WWW = Path.home() / "demo" / "www" / "tests" / "2026-11-models"
NUM, _, WHO = ROUND.removeprefix("round").partition("-")   # round3-sonnet: round 3, its cloud model sonnet
OUT = WWW / f"round{NUM}"   # every runner of round n writes into round<n>/
PRE = f"{WHO}-" if WHO else ""   # a cloud runner's part and why pages, apart from the local lanes'
PAGE_ONLY = os.environ.get("PAGE_ONLY") == "1"
NOW = time.time()
LANES = [d.name for d in sorted(SHARED.iterdir()) if d.is_dir() and re.fullmatch(r"[a-z]", d.name)] if SHARED.is_dir() else []
PARTS = [("1", "test 1"), ("2", "python"), ("2", "swift")]   # the runner's parts: tests 1, 2 (Python) and 3 (Swift)
NUMBER = {"python": "2", "swift": "3"}   # the pages' test numbers; run ids and folders keep test2-<model>-<language>


def read(p):
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def tsv(p):
    return [l.split("\t") for l in read(p).splitlines()[1:] if l.strip()]


PREV = "an earlier round"   # where carried runs come from


class Lane:
    def __init__(self, name):
        self.name, d = name, SHARED / name
        self.dir = d
        self.gate = {r[0]: r for r in tsv(d / "test0.tsv")}
        self.t1 = {(r[0], r[1]): (r[2], r[3] if len(r) > 3 else "") for r in tsv(d / "test1.tsv")}
        self.t2 = {(r[0], r[1], r[2]): (r[3], r[4] if len(r) > 4 else "", r[5] if len(r) > 5 else "")
                   for r in tsv(d / "test2.tsv")}
        self.ms = {}
        for l in read(d / "runs.jsonl").splitlines():
            try:
                m = json.loads(l)
            except ValueError:
                continue
            self.ms.setdefault(m.get("run", ""), []).append(m)
        try:
            self.pid = int(read(d / "runner.lock" / "pid"))
            os.kill(self.pid, 0)
            self.alive = True
        except (OSError, ValueError):
            self.pid, self.alive = None, False
        self.end = read(d / "end").strip()
        self.now = read(d / "now").split() if self.alive else []
        self.trace = None   # the milestone running now: the lane's newest trace that hasn't ended
        u = Path.home() / ".test-usage" / "2026-11-models" / f"{ROUND}-{name}"
        tr = sorted(u.glob("*.trace"), key=lambda p: p.stat().st_mtime) if self.alive and u.is_dir() else []
        if tr:
            last = read(tr[-1]).strip().splitlines()[-1:]
            if last and "Hermes exited" not in last[0] and "ended:" not in last[0]:
                st = tr[-1].stat()
                self.trace = (tr[-1].stem, int(NOW - getattr(st, "st_birthtime", st.st_mtime)))


lanes = {n: Lane(n) for n in LANES}
# The blind review's grades (grades/test1.tsv): (round, model, run) -> (fit, rank, of, note)
GRADES = {}
for l in read(T / "grades" / "test1.tsv").splitlines():
    c = l.split("\t")
    if len(c) == 7 and not l.startswith("#") and c[0] != "round":
        GRADES[(c[0], c[1], c[2])] = tuple(c[3:])
carried = {(r[0], r[1]): (r[2], r[3] if len(r) > 3 else "") for r in tsv(SHARED / "carried" / "test1.tsv")}


def owner(name, part):
    return read(SHARED / "claims" / f"{name}-{part}" / "lane").strip()


def mins(s):
    return f"{s // 60} min" if s < 5400 else f"{s // 3600} h {s % 3600 // 60} min"


def cell(kind, text, sub="", link="", rank="", note=""):
    body = (f'<span class="rank">{html.escape(rank)}</span>' if rank else "") + f"<b>{html.escape(text)}</b>" \
        + (f"<small>{html.escape(sub)}</small>" if sub else "")
    if link:
        body = f'<a href="{link}">{body}</a>'
    if note:
        body += f'<small class="note">{html.escape(note)}</small>'
    return f'<td class="{kind}">{body}</td>'


def why_link(lane, rid):
    """The why file of the run's last milestone that didn't pass, as a page link."""
    ms = lane.ms.get(rid, [])
    bad = [m for m in ms if m.get("outcome") != "pass"]
    if not bad:
        return ""
    m = bad[-1]
    files = sorted((lane.dir / "why").glob(f"{m['run']}-{m['milestone']}-*.md"), key=lambda p: p.stat().st_mtime) \
        if (lane.dir / "why").is_dir() else []
    files = [f for f in files if re.fullmatch(r".*-\d+", f.stem)]
    return f"why/{PRE}{lane.name}-{files[-1].stem}.html" if files else ""


def progress(lane, rid, test):
    if test == "1":
        ms = lane.ms.get(rid, [])
        total = 4
    else:
        ms = lane.ms.get(rid, [])
        steps = T / "test2" / "plans" / os.environ.get("PLAN", "") / "steps.tsv"
        total = sum(1 for l in read(steps).splitlines() if l.split("\t")[0] == rid.split("-")[-2]) or "?"
    if test != "1":   # a build runs every step: count the steps done
        return len(ms), total
    return sum(1 for m in ms if m.get("outcome") == "pass"), total


def results_of(lane_name, test, lang):
    """(name, run) -> (result, where): the lane's own, over test 1 runs an earlier round carried in"""
    old = carried if test == "1" else {}
    lane = lanes.get(lane_name)
    if not lane:
        return dict(old)
    return {**old, **(lane.t1 if test == "1" else {(k[0], k[2]): v for k, v in lane.t2.items() if k[1] == lang})}


CARRIED = []   # the runs shown that an earlier round settled


def score_of(text):
    """'12 of 16' -> (12, 16)"""
    m = re.match(r"(\d+) of (\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# a lane whose end the owner called (sherlock.sh never writes this): its runs not done never will be
OWNER_ENDED = any(read(SHARED / n / "end").startswith("stopped: the owner") for n in ("a", "b"))


def run_cell(name, test, lang, r, lane_name):
    res = results_of(lane_name, test, lang)
    lane = lanes.get(lane_name)
    rid = f"test1-{name}-r{r}" if test == "1" else f"test2-{name}-{lang}-r{r}"
    want = ["1", name, str(r)] if test == "1" else ["2", name, lang, str(r)]
    if lane and lane.now == want:
        ok, total = progress(lane, rid, test)
        word = "passed" if test == "1" else "done"
        sub = f"{ok} of {total} steps {word}"
        if lane.trace and lane.trace[0].startswith(rid):
            step = lane.trace[0][len(rid) + 1:].rsplit("-", 1)[0]
            sub = f"{step.replace('-', ' ')}, {mins(lane.trace[1])} in · {ok}/{total} {word}"
        return cell("run", "running", sub)
    got = res.get((name, str(r)))
    if got and test != "1" and got[0] != "machine-failed" and len(got) > 2 and got[2]:
        p, n = score_of(got[2])   # a build: its score, the hidden tests its last step passes
        link = why_link(lane, rid) if lane else ""
        return cell("ok" if p == n else "inc" if p == 0 else "part", f"{p} of {n}", "hidden tests passed", link)
    if got:
        result, where = got[:2]
        old = test == "1" and carried.get((name, str(r))) == got and not (lane and (name, str(r)) in lane.t1)
        if old:
            CARRIED.append(rid)
        if result == "complete":
            gr = GRADES.get((ROUND, name, str(r))) if test == "1" else None
            if gr:
                fit, rank, of, note = gr
                if fit == "yes":
                    return cell("ok", "complete", "fit to build from", rank=f"#{rank} of {of}", note=note)
                return cell("bad", "failed", "plan not fit to build from", rank=f"#{rank} of {of}", note=note)
            return cell("ok", "complete", "awaiting review" if test == "1" else "")
        if old:
            return cell("bad", "failed", f"at {where}, {PREV}" if where else PREV)
        link = why_link(lane, rid) if lane else ""
        if result == "machine-failed":
            return cell("mach", "machine fault", where, link)
        return cell("inc", "incomplete", f"stopped at {where}" if where else "", link)   # nothing finished, so nothing to rank
    if r == 3 and ONLY:   # a cloud round: the third run only when the first two differ
        a, b = res.get((name, "1")), res.get((name, "2"))
        if a and b and a[0] == b[0] and a[0] != "machine-failed":
            return cell("skip", "not needed", "runs 1 and 2 agree")
    if OWNER_ENDED:
        return cell("skip", "not run", "test ended by the owner")
    return cell("wait", "waiting")


models = []
# ROUND_MODELS "<name> <tests...>": the round's own rows, over models.txt's tests column (cloud.sh)
ONLY = os.environ.get("ROUND_MODELS", "").split()
for line in (T / "models.txt").read_text().splitlines():
    c = line.split()
    if c and not line.startswith("#"):
        if ONLY:
            c = c[:4] + ONLY[1:] if c[0] == ONLY[0] else c[:4]
        tests = set(c[4:])
        tests |= {"python", "swift"} if "2" in tests else ({"2"} if tests & {"python", "swift"} else set())
        if c[4:]:   # a model with no tests this round isn't shown
            models.append((c[0], c[1], tests))

def doing(lane):
    n = lane.now
    if not n:
        return ""
    if n[0] == "w":
        return "waiting for " + " ".join(n[1:])
    if n[0] == "p":
        return "preflight: one trivial step to prove the runner works"
    if n[0] == "0":
        return f"{n[1]}: the gate"
    if n[0] == "1":
        return f"{n[1]}: test 1, project management, run {n[2]}"
    if n[0] == "2":
        return f"{n[1]}: test {NUMBER.get(n[2], '2')}, {n[2].capitalize()}, run {n[3]}"
    return "waiting for Swift to be free" if n[1:] == ["swift"] else "waiting: the other lane holds what is left, or a gate is due"


A = lanes.get("a")
def ctx_note(g):
    """The context the gate measured and set in Hermes (round 4 on; rounds 1-3 ran at 64K)."""
    return f"context {int(g[8]) // 1024}K" if g and len(g) > 9 and g[8].isdigit() else ""


CARRIED_GATE = read(SHARED / "gate-carried").split()
rows, cells, counts = [], {}, {"ok": 0, "bad": 0, "inc": 0, "mach": 0, "run": 0, "wait": 0}
for name, model, tests in models:
    g = A.gate.get(name) if A else None
    note = ctx_note(g)
    tds = [f'<th class="name">{html.escape(name)}<small>{html.escape(model.split("/")[-1])}</small>'
           + (f'<small>{html.escape(note)}</small>' if note else "") + '</th>']
    if A and A.now == ["0", name]:
        tds.append(cell("gate", "running", "loading, 20 calls, the long prompt, then a Hermes job"))
    elif not g and ONLY and name == ONLY[0]:
        tds.append(cell("gate", "no gate", "a cloud model, no local server"))
    elif not g:
        tds.append(cell("gate", "waiting"))
    elif g[-1] == "yes":
        job = g[9] if len(g) > 10 else ""   # every passing model's job completes with a subagent: show only an exception
        tds.append(cell("gate", "passed", f"{g[7]} tok/s" + (f"; Hermes job {job}" if job and job != "complete, with a subagent" else "")))
    elif g[2] == "no":
        tds.append(cell("gate", "failed", "didn't load"))
    elif g[6] != "20" or g[5] != "yes":
        tds.append(cell("gate", "failed", f"{g[6] or 0} of 20 calls parsed"))
    elif not g[7] or float(g[7]) < 15:
        tds.append(cell("gate", "too slow", f"{g[7]} tok/s, under 15"))
    elif len(g) > 9 and not g[8]:
        tds.append(cell("gate", "failed", "lost the long prompt at 128K and 64K"))
    else:
        tds.append(cell("gate", "failed", f"Hermes job {g[9]}" if len(g) > 9 else ""))
    gate_failed = g is not None and g[-1] != "yes"
    if name in CARRIED_GATE:   # passed in earlier iterations; this one's single reading was borderline (owner, 12 Nov)
        tds[1] = cell("gate", "passed before", f"this time: {g[7]} tok/s, {g[6]} of 20 parsed" if g else "")
        gate_failed = False
    for test, lang in PARTS:
        part = "1" if test == "1" else lang
        lane_name = owner(name, part)
        here = test in tests and (test == "1" or lang in tests)
        for r in (1, 2, 3):
            if not here:
                tds.append('<td class="na"></td>')
            elif gate_failed:
                tds.append(cell("skip", "not run", "failed the gate"))
            else:
                tds.append(run_cell(name, test, lang, r, lane_name))
        if here and not gate_failed:
            got = [v[0] for k, v in results_of(lane_name, test, lang).items() if k[0] == name]
            if test == "1":   # a plan the review found not fit to build from is a failed run
                got = ["failed" if x == "complete" and GRADES.get((ROUND, name, k[1]), ("yes",))[0] != "yes" else x
                       for (k, v), x in zip([(k, v) for k, v in results_of(lane_name, test, lang).items() if k[0] == name], got)]
            n = sum(1 for x in got if x == "complete")
            score = f"{n}/{len(got)}" if got else ""
            if test != "1":   # builds: the mean share of hidden tests passed, and its range across runs
                pcts = [100 * p // q for p, q in (score_of(v[2]) for k, v in results_of(lane_name, test, lang).items()
                                                  if k[0] == name and len(v) > 2 and v[2]) if q]
                score = (f"{sum(pcts) // len(pcts)}%" + (f" ({min(pcts)}–{max(pcts)})" if len(pcts) > 1 else "")) if pcts else ""
            where = PREV if not lane_name and got else ""   # one model host: only carried runs say where
            tds.append(f'<td class="score">{score}' + (f'<small>{html.escape(where)}</small>' if where else "") + '</td>')
        else:
            tds.append('<td class="score"></td>')
    runs = "".join(tds[2:])
    for k in counts:
        counts[k] += runs.count(f'<td class="{k}"')
    # A cloud runner that waits (night hours, a usage limit, its preflight) shows it in the cell it runs next
    lane = lanes.get("a")
    if ONLY and lane and lane.alive and lane.now and lane.now[0] in ("w", "p"):
        why = doing(lane)
        for i, t in enumerate(tds):
            if i >= 2 and '<td class="wait">' in t:
                tds[i] = cell("run", "next", why)
                break
    rows.append(f"<tr>{''.join(tds)}</tr>")
    cells[name] = tds


lane_lines = []
for n, lane in lanes.items():
    if lane.alive:
        lane_lines.append(f"running · {doing(lane)}")
    else:
        lane_lines.append(lane.end or "not running, and recorded no end: killed, or Sherlock restarted")
alive = any(l.alive for l in lanes.values())
ends = [l.end for l in lanes.values()]
if alive:
    state, banner_class = "running", "run"
elif ends and all(e == "done" for e in ends):
    state, banner_class = "done", "ok"
elif any(e.startswith("incomplete") for e in ends):
    state, banner_class = "incomplete", "mach"
else:
    state, banner_class = "stopped", "bad"
try:
    deadline = int(read(SHARED / "deadline"))
except ValueError:
    deadline = None
facts = [f"Updated {time.strftime('%a %d %b %H:%M:%S', time.localtime(NOW))}", ROUND.replace("round", "round ")]
if deadline:
    left = deadline - NOW
    facts.append(f"time limit {time.strftime('%a %d %b %H:%M', time.localtime(deadline))}"
                 + (f" ({mins(int(left))} left)" if left > 0 else " (reached)"))
facts.append(f"{counts['ok']} complete · {counts['bad']} failed · {counts['inc']} incomplete · {counts['mach']} machine faults · {counts['wait']} waiting"
             + (f" · {len(CARRIED)} run{'s' if len(CARRIED) != 1 else ''} carried from {PREV}" if CARRIED else ""))

def test_of(stem):
    """A why file's test, by the pages' numbers: test2-<model>-swift-r1-M1-0 is test 3, Swift."""
    k = stem.split("-")[0]
    if k == "test2":
        lang = next((x for x in ("python", "swift") if f"-{x}-r" in stem), "")
        return f"Test {NUMBER.get(lang, '2')} · {lang.capitalize()}"
    return {"test1": "Test 1 · project management", "gate": "The gate", "preflight": "Preflight"}.get(k, k)


recent = read(LOG).splitlines()[-30:]
d = ROUND.removeprefix("round")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "why").mkdir(exist_ok=True)
for n, lane in ({} if PAGE_ONLY else lanes).items():
    for f in (lane.dir / "why").glob("*.md") if (lane.dir / "why").is_dir() else []:
        dest = OUT / "why" / f"{PRE}{n}-{f.stem}.html"
        if not dest.exists() or dest.stat().st_mtime < f.stat().st_mtime:
            dest.write_text(f'<!doctype html><meta charset="utf-8"><title>{html.escape(f.stem)}</title>'
                            f'<body style="font:13px/1.45 ui-monospace,Menlo,monospace;padding:16px;white-space:pre-wrap">'
                            f'<a href="../">‹ round {NUM}</a>\n\n<b>{html.escape(test_of(f.stem))}</b>\n\n'
                            f'{html.escape(f.read_text(errors="replace"))}</body>')
part = {"round": d, "made": int(NOW), "alive": alive, "state": state, "banner": banner_class, "lanes": lane_lines,
        "facts": facts, "cells": cells, "log": recent}
if not PAGE_ONLY:
    tmp = OUT / f"part.json.{os.getpid()}.tmp"   # two lanes write at once: each its own
    tmp.write_text(json.dumps(part))
    tmp.rename(OUT / f"part{'-' + WHO if WHO else ''}.json")

# The round's page: its parts
parts = []
for f in OUT.glob("part*.json"):
    try:
        parts.append(json.loads(f.read_text()))
    except ValueError:
        pass
parts.sort(key=lambda p: (int(p["round"].split("-")[0]), "-" in p["round"], p["round"]))
ncol = 2 + 4 * len(PARTS)
body, logs, groups = [], [], set()
for p in parts:
    num, _, who = p["round"].partition("-")   # round 1's local lanes are "1", its cloud models "1-sonnet"
    name, _, own = who.partition("-")   # "terra-own": Terra building from its own plan
    label = (f"{name.capitalize()} (cloud{', ' + own + ' plan' if own else ''})" if who else "local models")
    logs.append(f'<details><summary>{html.escape(label)}: runner log, last lines</summary><pre>{html.escape(chr(10).join(p["log"]))}</pre></details>')
# One row a model: each column from whichever runner has that test for it (Terra's test 1 from its
# test 1 runner, its test 2 from its build runner); an empty or waiting cell gives way to one with news
def weight(td):
    return 0 if 'class="na"' in td else 1 if 'class="wait"' in td or td == '<td class="score"></td>' else 2   # an empty score: no runs yet, as waiting


order = [l.split()[0] for l in (T / "models.txt").read_text().splitlines() if l.split() and not l.startswith("#")]
TEST2 = range(6, 6 + 8)   # the Python and Swift columns (after name, gate and test 1's four)
merged, halves = {}, {}   # halves: name -> {"own"/"local": tds}, a cloud model's builds of each plan
for p in parts:
    kind = p["round"].rsplit("-", 1)[-1] if p["round"].count("-") >= 2 else ""
    for n, tds in p.get("cells", {}).items():
        if kind in ("own", "local"):
            halves.setdefault(n, {})[kind] = tds
            tds = [t if i not in TEST2 else '<td class="na"></td>' for i, t in enumerate(tds)]
        if n not in merged:
            merged[n] = list(tds)
        else:
            for i, (a, b) in enumerate(zip(merged[n], tds)):
                if weight(b) > weight(a):
                    merged[n][i] = b

def half(td, label):
    m = re.match(r'<td class="([a-z]+)">(.*)</td>$', td, re.S)
    kind, inner = (m.group(1), m.group(2)) if m else ("wait", "")
    if kind == "na" or (kind == "score" and not inner):
        kind, inner = ("wait", "<b>not started</b>") if kind == "na" else ("score", "")
    return f'<div class="half {kind}"><small class="plan">{label}</small>{inner}</div>'


for n, hs in halves.items():   # each test 2 cell split: own plan above, local plan below
    for i in TEST2:
        merged[n][i] = '<td class="split">' + "".join(half(hs[k][i] if k in hs else '<td class="na"></td>', f"{k} plan") for k in ("own", "local")) + "</td>"
body = [f"<tr>{''.join(merged[n])}</tr>" for n in sorted(merged, key=lambda n: order.index(n) if n in order else 99)]
head = "".join(f'<th colspan="4">{t}</th>' for t in ("Test 1 · project management", "Test 2 · Python", "Test 3 · Swift"))
sub = "".join('<th>run 1</th><th>run 2</th><th>run 3</th><th title="complete runs / runs done">score</th>' for _ in range(3))
more = "".join(f' · <a href="{f.name}">{html.escape(re.search(r"<title>(.*?)</title>", read(f), re.S).group(1) if "<title>" in read(f) else f.stem)}</a>'
               for f in sorted(OUT.glob("*.html")) if f.name != "index.html")   # the round's other pages (round 4's context probe)
page = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model tests · round {NUM}</title>
<style>
:root {{ --bg:#f6f6f4; --fg:#1d1d1b; --mute:#6b6b66; --line:#d9d9d4; --card:#fff;
  --ok:#d7f0dc; --okf:#14532d; --bad:#fbd5d5; --badf:#7f1d1d; --mach:#fde7c4; --machf:#7c4a03;
  --run:#d6e6fb; --runf:#173f78; --wait:#ececea; --waitf:#77776f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161615; --fg:#ececea; --mute:#9a9a94; --line:#33332f; --card:#1f1f1d;
  --ok:#163a22; --okf:#9ee2b0; --bad:#4a1c1c; --badf:#f6b3b3; --mach:#45320f; --machf:#f5cf8c;
  --run:#17304f; --runf:#a9cbf6; --wait:#262624; --waitf:#8b8b84; }} }}
body {{ margin:0; padding:20px 16px; background:var(--bg); color:var(--fg); font:14px/1.4 -apple-system, system-ui, sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
.facts {{ color:var(--mute); margin:0 0 12px; }}
.wrap {{ overflow-x:auto; }}
table {{ border-collapse:separate; border-spacing:3px; }}
th {{ font-weight:600; font-size:12px; color:var(--mute); padding:2px 4px; white-space:nowrap; }}
th.name {{ text-align:left; color:var(--fg); font-size:14px; padding-right:10px; }}
th.name small {{ display:block; font-weight:400; color:var(--mute); font-size:11px; }}
td {{ min-width:92px; padding:6px 8px; border-radius:6px; vertical-align:top; font-size:13px; }}
td b {{ display:block; font-weight:600; }}
td small {{ display:block; font-size:11px; opacity:.85; }}
td.score small {{ font-weight:400; color:var(--mute); }}
td a {{ color:inherit; text-decoration:none; display:block; }}
td a:hover b {{ text-decoration:underline; }}
td a b::after {{ content:" ›"; }}
.ok {{ background:var(--ok); color:var(--okf); }} .bad {{ background:var(--bad); color:var(--badf); }}
.inc {{ background:color-mix(in srgb, var(--bad) 30%, transparent); color:var(--badf); }}
.part {{ background:color-mix(in srgb, var(--ok) 35%, transparent); color:var(--okf); }}
.mach {{ background:var(--mach); color:var(--machf); }} .wait {{ background:var(--wait); color:var(--waitf); }}
.run {{ background:var(--run); color:var(--runf); animation:pulse 2s ease-in-out infinite; }}
.rank {{ display:inline-block; margin:0 0 4px; padding:2px 8px; border-radius:5px; font-size:16px; font-weight:700; color:#111; }}
.ok .rank {{ background:color-mix(in srgb, var(--ok) 45%, #fff); }}
.bad .rank {{ background:color-mix(in srgb, var(--bad) 45%, #fff); }}
td small.note {{ margin-top:4px; font-size:11px; line-height:1.3; opacity:.8; max-width:260px; white-space:normal; }}
td.split {{ padding:0; background:transparent; }}
td.gate {{ background:transparent; animation:none; }}
.half {{ padding:5px 8px; border-radius:6px; margin:0 0 3px; }}
.half:last-child {{ margin:0; }}
.half b {{ display:block; font-weight:600; }}
.half small {{ display:block; font-size:11px; opacity:.85; }}
.half small.plan {{ font-weight:600; text-transform:uppercase; letter-spacing:.03em; opacity:.7; }}
.half.score {{ text-align:center; font-weight:700; color:var(--fg); background:transparent; }}
.skip {{ background:transparent; color:var(--waitf); border:1px dashed var(--line); }}
.na {{ background:transparent; min-width:0; }}
td.score {{ min-width:30px; text-align:center; font-weight:700; color:var(--fg); background:transparent; }}
@keyframes pulse {{ 50% {{ opacity:.6; }} }}
pre {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; overflow-x:auto; font-size:12px; }}
th.group {{ text-align:left; color:var(--fg); font-size:15px; padding:14px 4px 4px; }}
summary {{ cursor:pointer; font-weight:600; margin-top:12px; }}
</style>
</head><body>
<p><a href="/tests/">← All tests</a></p>
<h1>Model tests · round {NUM}</h1>
<p class="facts">Updated {time.strftime('%a %d %b %H:%M:%S', time.localtime(NOW))}. Reload to refresh.{more}</p>
<div class="wrap"><table>
<tr><th></th><th>Gate</th>{head}</tr>
<tr><th></th><th></th>{sub}</tr>
{"".join(body)}
</table></div>
{"".join(logs)}
</body></html>
"""
tmp = OUT / f"index.html.{os.getpid()}.tmp"
tmp.write_text(page)
tmp.rename(OUT / "index.html")

# The public copy (pages.sh, GitHub Pages): at most every 10 min, in the background, never in the runner's way
STAMP = Path.home() / "tests-site" / "pages.stamp"
if not STAMP.exists() or NOW - STAMP.stat().st_mtime > 600:
    import subprocess
    STAMP.parent.mkdir(exist_ok=True)
    STAMP.touch()
    subprocess.Popen(["bash", str(T.parent / "pages.sh")], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
