"""The round's status page, on Sherlock: python3 status.py <run folder>
Writes ~/demo/www/tests/2026-10-config/round<n>/index.html (ROUND), which Sherlock's demo server
shows at http://192.168.50.100:18100/tests/2026-10-config/round<n>/ (Dr Watson only), under the
tests index, each why/ file beside it as a page. Each lane's runner writes it every
10 s while it runs, and once more as it ends. One row a model, one cell a permutation (the
gate; test 1 runs; test 2 runs per language): its result, or what it is doing now, and under
each score the server that ran it. The owner reloads it by hand; loaded more than a minute
after it was last written, it says so in red."""
import html
import json
import os
import re
import sys
import time
from pathlib import Path

T = Path(__file__).resolve().parent
ROUND = os.environ.get("ROUND", "round5")
SHARED = T / "results" / ROUND
LOG = Path(sys.argv[1]) / "log.txt"
WWW = Path.home() / "demo" / "www" / "tests" / "2026-10-config"
OUT = WWW / ROUND
NOW = time.time()
LANES = [d.name for d in sorted(SHARED.iterdir()) if d.is_dir() and re.fullmatch(r"[a-z]", d.name)] if SHARED.is_dir() else []
PARTS = [("1", "test 1"), ("2", "python"), ("2", "swift")]


def read(p):
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def tsv(p):
    return [l.split("\t") for l in read(p).splitlines()[1:] if l.strip()]


PREV = "an earlier round"   # where carried runs come from
servers = {"a": "Adlerbot", "carried": PREV}
for l in read(SHARED / "servers").splitlines():
    if len(l.split()) == 2:
        servers[l.split()[0]] = l.split()[1]


class Lane:
    def __init__(self, name):
        self.name, d = name, SHARED / name
        self.dir = d
        self.gate = {r[0]: r for r in tsv(d / "test0.tsv")}
        self.t1 = {(r[0], r[1]): (r[2], r[3] if len(r) > 3 else "") for r in tsv(d / "test1.tsv")}
        self.t2 = {(r[0], r[1], r[2]): (r[3], r[4] if len(r) > 4 else "") for r in tsv(d / "test2.tsv")}
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
        u = Path.home() / ".test-usage" / f"{ROUND}-{name}"
        tr = sorted(u.glob("*.trace"), key=lambda p: p.stat().st_mtime) if self.alive and u.is_dir() else []
        if tr:
            last = read(tr[-1]).strip().splitlines()[-1:]
            if last and "Hermes exited" not in last[0] and "ended:" not in last[0]:
                st = tr[-1].stat()
                self.trace = (tr[-1].stem, int(NOW - getattr(st, "st_birthtime", st.st_mtime)))


lanes = {n: Lane(n) for n in LANES}
carried = {(r[0], r[1]): (r[2], r[3] if len(r) > 3 else "") for r in tsv(SHARED / "carried" / "test1.tsv")}


def owner(name, part):
    return read(SHARED / "claims" / f"{name}-{part}" / "lane").strip()


def mins(s):
    return f"{s // 60} min" if s < 5400 else f"{s // 3600} h {s % 3600 // 60} min"


def cell(kind, text, sub="", link=""):
    body = f"<b>{html.escape(text)}</b>" + (f"<small>{html.escape(sub)}</small>" if sub else "")
    if link:
        body = f'<a href="{link}">{body}</a>'
    return f'<td class="{kind}">{body}</td>'


def why_link(lane, rid):
    """The why file of the run's last milestone that didn't pass, as a page link."""
    ms = lane.ms.get(rid, []) if not rid.startswith("test1") else \
        [m for k, v in lane.ms.items() if k.startswith(rid + "-") for m in v]
    bad = [m for m in ms if m.get("outcome") != "pass"]
    if not bad:
        return ""
    m = bad[-1]
    files = sorted((lane.dir / "why").glob(f"{m['run']}-{m['milestone']}-*.md"), key=lambda p: p.stat().st_mtime) \
        if (lane.dir / "why").is_dir() else []
    files = [f for f in files if re.fullmatch(r".*-\d+", f.stem)]
    return f"why/{lane.name}-{files[-1].stem}.html" if files else ""


def progress(lane, rid, test):
    if test == "1":
        ms = [m for k, v in lane.ms.items() if k.startswith(rid + "-") for m in v]
        total = 18
    else:
        ms = lane.ms.get(rid, [])
        total = 6 if rid.split("-")[-2] == "python" else 5
    return sum(1 for m in ms if m.get("outcome") == "pass"), total


def results_of(lane_name, test, lang):
    """(name, run) -> (result, where): the lane's own, over test 1 runs an earlier round carried in"""
    old = carried if test == "1" else {}
    lane = lanes.get(lane_name)
    if not lane:
        return dict(old)
    return {**old, **(lane.t1 if test == "1" else {(k[0], k[2]): v for k, v in lane.t2.items() if k[1] == lang})}


CARRIED = []   # the runs shown that an earlier round settled


def run_cell(name, test, lang, r, lane_name):
    res = results_of(lane_name, test, lang)
    lane = lanes.get(lane_name)
    rid = f"test1-{name}-r{r}" if test == "1" else f"test2-{name}-{lang}-r{r}"
    want = ["1", name, str(r)] if test == "1" else ["2", name, lang, str(r)]
    if lane and lane.now == want:
        ok, total = progress(lane, rid, test)
        sub = f"{ok} of {total} steps passed"
        if lane.trace and lane.trace[0].startswith(rid):
            step = lane.trace[0][len(rid) + 1:].rsplit("-", 1)[0]
            sub = f"{step.replace('-', ' ')}, {mins(lane.trace[1])} in · {ok}/{total} passed"
        return cell("run", "running", sub)
    got = res.get((name, str(r)))
    if got:
        result, where = got
        old = test == "1" and carried.get((name, str(r))) == got and not (lane and (name, str(r)) in lane.t1)
        if old:
            CARRIED.append(rid)
        if result == "complete":
            return cell("ok", "complete", f"from {PREV}" if old else "")
        if old:
            return cell("bad", "failed", f"at {where}, {PREV}" if where else PREV)
        link = why_link(lane, rid) if lane else ""
        if result == "machine-failed":
            return cell("mach", "machine fault", where, link)
        return cell("bad", "failed", f"at {where}" if where else "", link)
    if r == 3:
        a, b = res.get((name, "1")), res.get((name, "2"))
        if a and b and a[0] == b[0] and a[0] != "machine-failed":
            return cell("skip", "not needed", "runs 1 and 2 agree")
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

A = lanes.get("a")
rows, counts = [], {"ok": 0, "bad": 0, "mach": 0, "run": 0, "wait": 0}
for name, model, tests in models:
    g = A.gate.get(name) if A else None
    tds = [f'<th class="name">{html.escape(name)}<small>{html.escape(model.split("/")[-1])}</small></th>']
    if A and A.now == ["0", name]:
        tds.append(cell("run", "running", "loading, then 20 calls"))
    elif not g and ONLY and name == ONLY[0]:
        tds.append(cell("skip", "no gate", "a cloud model, no local server"))
    elif not g:
        tds.append(cell("wait", "waiting"))
    elif g[-1] == "yes":
        tds.append(cell("ok", "passed", f"{g[7]} tok/s" if len(g) > 7 and g[7] else ""))
    elif g[2] == "no":
        tds.append(cell("bad", "failed", "didn't load"))
    elif g[6] != "20" or g[5] != "yes":
        tds.append(cell("bad", "failed", f"{g[6] or 0} of 20 calls parsed"))
    else:
        tds.append(cell("bad", "too slow", f"{g[7]} tok/s, under 15"))
    gate_failed = g is not None and g[-1] != "yes"
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
            n = sum(1 for x in got if x == "complete")
            where = servers.get(lane_name, lane_name)
            score = f"{n}/{len(got)}" if got else ""
            if not lane_name and got:
                where = PREV
            tds.append(f'<td class="score">{score}<small>{html.escape(where)}</small></td>' if lane_name or got else '<td class="score"></td>')
        else:
            tds.append('<td class="score"></td>')
    runs = "".join(tds[2:])
    for k in counts:
        counts[k] += runs.count(f'<td class="{k}"')
    rows.append(f"<tr>{''.join(tds)}</tr>")


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
        return f"{n[1]}: test 2, {n[2]}, run {n[3]}"
    return "waiting for Swift to be free" if n[1:] == ["swift"] else "waiting: the other lane holds what is left, or a gate is due"


lane_lines = []
for n, lane in lanes.items():
    srv = servers.get(n, n)
    if lane.alive:
        lane_lines.append(f"{srv}: running · {doing(lane)}")
    else:
        lane_lines.append(f"{srv}: {lane.end or 'not running, and recorded no end: killed, or Sherlock restarted'}")
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
facts.append(f"{counts['ok']} complete · {counts['bad']} failed · {counts['mach']} machine faults · {counts['wait']} waiting"
             + (f" · {len(CARRIED)} run{'s' if len(CARRIED) != 1 else ''} carried from {PREV}" if CARRIED else ""))

recent = read(LOG).splitlines()[-30:]
head = "".join(f'<th colspan="4">{t}</th>' for t in ("Test 1 · project management", "Test 2 · Python", "Test 2 · Swift"))
sub = "".join('<th>run 1</th><th>run 2</th><th>run 3</th><th title="complete runs / runs done; the server under it">score</th>' for _ in range(3))
page = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test round</title>
<style>
:root {{ --bg:#f6f6f4; --fg:#1d1d1b; --mute:#6b6b66; --line:#d9d9d4; --card:#fff;
  --ok:#d7f0dc; --okf:#14532d; --bad:#fbd5d5; --badf:#7f1d1d; --mach:#fde7c4; --machf:#7c4a03;
  --run:#d6e6fb; --runf:#173f78; --wait:#ececea; --waitf:#77776f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161615; --fg:#ececea; --mute:#9a9a94; --line:#33332f; --card:#1f1f1d;
  --ok:#163a22; --okf:#9ee2b0; --bad:#4a1c1c; --badf:#f6b3b3; --mach:#45320f; --machf:#f5cf8c;
  --run:#17304f; --runf:#a9cbf6; --wait:#262624; --waitf:#8b8b84; }} }}
body {{ margin:0; padding:20px 16px; background:var(--bg); color:var(--fg); font:14px/1.4 -apple-system, system-ui, sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
.banner {{ padding:12px 14px; border-radius:8px; margin:12px 0; font-size:16px; }}
.banner b {{ text-transform:uppercase; letter-spacing:.04em; margin-right:8px; }}
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
.lanes {{ margin:0 0 12px; padding-left:18px; color:var(--mute); }}
td a {{ color:inherit; text-decoration:none; display:block; }}
td a:hover b {{ text-decoration:underline; }}
td a b::after {{ content:" ›"; }}
.ok {{ background:var(--ok); color:var(--okf); }} .bad {{ background:var(--bad); color:var(--badf); }}
.mach {{ background:var(--mach); color:var(--machf); }} .wait {{ background:var(--wait); color:var(--waitf); }}
.run {{ background:var(--run); color:var(--runf); animation:pulse 2s ease-in-out infinite; }}
.skip {{ background:transparent; color:var(--waitf); border:1px dashed var(--line); }}
.na {{ background:transparent; min-width:0; }}
td.score {{ min-width:30px; text-align:center; font-weight:700; color:var(--fg); background:transparent; }}
.banner.run {{ animation:none; }}
@keyframes pulse {{ 50% {{ opacity:.6; }} }}
pre {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; overflow-x:auto; font-size:12px; }}
#stale {{ display:none; }}
summary {{ cursor:pointer; font-weight:600; margin-top:12px; }}
</style>
</head><body>
<p><a href="/tests/">← All tests</a></p>
<h1>Local model test round {html.escape(ROUND.removeprefix("round"))}</h1>
<div id="stale" class="banner bad"><b>Not updating</b><span></span></div>
<div class="banner {banner_class}"><b>{html.escape(state)}</b></div>
<ul class="lanes">{"".join(f"<li>{html.escape(l)}</li>" for l in lane_lines)}</ul>
<p class="facts">{" · ".join(html.escape(f) for f in facts)}</p>
<div class="wrap"><table>
<tr><th></th><th>Gate</th>{head}</tr>
<tr><th></th><th></th>{sub}</tr>
{"".join(rows)}
</table></div>
<details><summary>Runner log, last lines</summary>
<pre>{html.escape(chr(10).join(recent))}</pre>
</details>
<script>
var made = {int(NOW)}, live = {"true" if alive else "false"};
function check() {{
  var age = Math.round(Date.now() / 1000 - made);
  if (live && age > 60) {{
    var s = document.getElementById("stale");
    s.style.display = "block";
    s.querySelector("span").textContent = "No update for " + Math.round(age / 60) + " min: the runner has stopped writing this page (killed, or Sherlock asleep or restarted).";
  }}
}}
check();   // once, as the page loads: an open page left unrefreshed is not a stale runner
</script>
</body></html>
"""

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "why").mkdir(exist_ok=True)
for n, lane in lanes.items():
    for f in (lane.dir / "why").glob("*.md") if (lane.dir / "why").is_dir() else []:
        dest = OUT / "why" / f"{n}-{f.stem}.html"
        if not dest.exists() or dest.stat().st_mtime < f.stat().st_mtime:
            dest.write_text(f'<!doctype html><meta charset="utf-8"><title>{html.escape(f.stem)}</title>'
                            f'<body style="font:13px/1.45 ui-monospace,Menlo,monospace;padding:16px;white-space:pre-wrap">'
                            f'<a href="../">‹ the round</a>\n\n{html.escape(f.read_text(errors="replace"))}</body>')
tmp = OUT / "index.html.tmp"
tmp.write_text(page)
tmp.rename(OUT / "index.html")
