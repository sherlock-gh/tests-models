"""The tests' home page, on Sherlock: python3 site.py
Writes ~/demo/www/tests/, which Sherlock's demo server shows at http://192.168.50.100:18100/tests/
(the lab network): one row a test (from README.md's table), linking each round's page,
/tests/<test>/round<n>/, and, for the tests whose files publish.sh gathered, the files to
reproduce it at /tests/<test>/files/, each viewable and all in one download. Its input is
~/tests-site/kit/, those files at their paths under tests/, made by publish.sh, which then runs
this. The demo server empties ~/demo/www when it restarts: run publish.sh again then."""
import html
import re
import shutil
import tarfile
from pathlib import Path

KIT = Path.home() / "tests-site" / "kit"
WWW = Path.home() / "demo" / "www" / "tests"
STYLE = """:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--dim:#6b6b70;--line:#dcdcd8;--accent:#0b63ce}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--card:#1f1f22;--fg:#ececee;--dim:#9a9aa2;--line:#34343a;--accent:#6aa6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:64rem;margin:0 auto;padding:2rem 1rem 4rem}a{color:var(--accent)}.dim{color:var(--dim)}
table{border-collapse:collapse;width:100%;background:var(--card)}td,th{border:1px solid var(--line);padding:.5rem .7rem;text-align:left;vertical-align:top}
pre{background:var(--card);border:1px solid var(--line);padding:1rem;border-radius:.4rem;overflow-x:auto;font-size:.85rem}
section{background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:1.2rem 1.4rem;margin:0 0 1.5rem}
section h2{margin:0 0 .6rem;font-size:1.3rem}
.q{font-size:1.1rem;margin:0 0 1rem}h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin:1.4rem 0 .5rem}
section table td:first-child{white-space:nowrap;font-weight:600}ul.why{margin:0;padding-left:1.2rem}ul.why li{margin:.25rem 0}
dl.key{display:grid;grid-template-columns:max-content 1fr;gap:.4rem .8rem;margin:0}dl.key dd{margin:0}
.chip{display:inline-block;padding:.05rem .5rem;border-radius:.3rem;font-size:.85rem;font-weight:600}
.ok{background:#d7f0dc;color:#14532d}.bad{background:#fbd5d5;color:#7f1d1d}.inc{background:#fbe9e9;color:#7f1d1d}.mach{background:#fde7c4;color:#7c4a03}
table.top{margin:0 0 .6rem}table.top td:first-child{white-space:nowrap}"""


# What each test is, for the index: the question, its parts, why it's run this way, how to read
# its results page. The results pages show results only.
ABOUT = {
"2026-11-models": """
<p class=q>Which model should do each kind of work: planning, Python, Swift, a website?</p>
<p>Candidates: the local models on Adlerbot, run by Hermes. Sonnet and Terra (cloud) are for comparison only.</p>
<h3>The tests</h3>
<table><tr><th>Test</th><th>What the model does</th><th>Passes when</th></tr>
<tr><td>Gate</td><td>Loads and answers on Adlerbot</td><td>Loads at 64K context, 20 of 20 tool calls parse, 15 tok/s or faster</td></tr>
<tr><td>1 · Planning</td><td>Plans the house-cleaning problem with SpecKit: spec, plan, tasks, estimate</td><td>Every document complete, open questions listed in <code>questions.md</code>, and the blind review finds the plan fit to build both apps from</td></tr>
<tr><td>2 · Python</td><td>Builds the desktop app, a local web page, from the best local plan, one milestone at a time</td><td>Every milestone passes its hidden tests, earlier milestones' tests included</td></tr>
<tr><td>2 · Swift</td><td>Builds the mobile app's logic, a Swift package with no screens, the same way</td><td>Same as Python</td></tr>
<tr><td>Website</td><td>Builds a site from the owner's brief and images</td><td>The owner judges it against his own site</td></tr>
</table>
<h3>Why this way</h3>
<ul class=why>
<li><b>One problem, written with the owner.</b> The test measures planning, not guessing what the problem is.</li>
<li><b>Finished first, then quality.</b> Unfinished or unusable work doesn't help. Speed only breaks ties.</li>
<li><b>Each test drops models.</b> Time goes to the models that could be chosen.</li>
<li><b>Three runs each.</b> One run can be luck. A model needs 2 of 3; a gap smaller than a model's own run-to-run spread is a tie.</li>
<li><b>Crashes don't count.</b> If Hermes or the model server breaks, it is repaired and the work resumes.</li>
<li><b>Graded blind.</b> Graders don't see model names. Hidden tests check only what the plan says.</li>
<li><b>One plan for all builds.</b> So builds compare models, not plans. Cloud models also build their own plan.</li>
</ul>
<h3>Reading the results</h3>
<dl class=key>
<dt><span class="chip ok">complete</span></dt><dd>Finished and usable.</dd>
<dt><span class="chip bad">failed</span></dt><dd>Finished but not usable. F-numbers (F1, F2…) name the checklist items it misses.</dd>
<dt><span class="chip inc">incomplete</span></dt><dd>Stopped before the end; the cell says where.</dd>
<dt><span class="chip mach">machine fault</span></dt><dd>Broke for a reason that isn't the model's; redone.</dd>
<dt>#n of N</dt><dd>Rank among finished runs; #1 is best.</dd>
<dt>2/3</dt><dd>Complete runs out of runs done; the server that ran them is under it.</dd>
<dt>own / local plan</dt><dd>A cloud model's build cell is split: its own plan above, the local plan below.</dd>
<dt>not needed</dt><dd>A cloud model skips run 3 when runs 1 and 2 agree.</dd>
</dl>
""",
"2026-10-config": """
<p class=q>Which local setup (engine, model, quantization, thinking, harness) can do planning and real Python and Swift builds?</p>
<h3>The tests</h3>
<table><tr><th>Test</th><th>What the model did</th><th>Passed when</th></tr>
<tr><td>Gate</td><td>Loaded and answered on Adlerbot</td><td>Loaded at 64K context, 20 of 20 tool calls parsed, 15 tok/s or faster</td></tr>
<tr><td>1 · Planning</td><td>Two proposals, then spec, plan and tasks for two small apps</td><td>Every document complete, and the blind review found it fit to send</td></tr>
<tr><td>2 · Python</td><td>Built an expense tracker in 6 milestones</td><td>Every milestone passed its hidden tests, earlier ones included</td></tr>
<tr><td>2 · Swift</td><td>Built a habit-tracking package in 5 milestones</td><td>Same as Python</td></tr>
</table>
<h3>Why this way</h3>
<ul class=why>
<li><b>Each test dropped setups.</b> The pick came from whichever survived.</li>
<li><b>Finished first, then quality.</b> Speed only broke ties.</li>
<li><b>Production as the reference.</b> Every model ran with production's settings (thinking off, Hermes at 64K), so a difference is the model's.</li>
<li><b>Three runs each.</b> A setup needed 2 of 3; run 3 ran only when runs 1 and 2 disagreed.</li>
<li><b>Crashes didn't count.</b> They were repaired and the work resumed.</li>
<li><b>Hidden checks.</b> Models never saw the tests or rubrics.</li>
</ul>
<h3>Reading the results</h3>
<dl class=key>
<dt><span class="chip ok">complete</span></dt><dd>Finished the whole piece of work.</dd>
<dt><span class="chip bad">failed</span></dt><dd>The model's own failure: failed a check, stopped, or ran out of time.</dd>
<dt><span class="chip mach">machine fault</span></dt><dd>Broke for a reason that isn't the model's; redone.</dd>
</dl>
""",
}
# Each test's passes, oldest first: what changed and what it showed
ITERATIONS = {
"2026-11-models": [
 ("Iteration 1", "11 Nov", "First pass: the gate, and planning by every local model, Sonnet and Terra. Terra also built its own plan. Flash-Next stopped 2 of 3 runs by saying what it would do next instead of doing it."),
 ("Iteration 2", "11–12 Nov", "One change: Hermes tells models not to end a turn by announcing the next step. Flash-Next then finished 3 of 3. In the blind review only Terra's plans were fit to build from, and the problem left 10 decisions open."),
 ("Iteration 3", "12–13 Nov", "The owner settled the 10 open decisions and added rules to the problem; each step names its output file and lists open questions. Laguna XS dropped. Fit plans: Sonnet and Terra, and Flash-Next run 1, the only local one."),
],
"2026-10-config": [
 ("Round 1", "25–31 Oct", "Every setup on every test. About half the failures were the test's own faults (a hang watch that missed the second server, a build cache breaking Swift checks, hidden tests asking for what the spec didn't say). Fixed before round 2."),
 ("Round 2", "2–7 Nov", "The fixed test, on two servers at once, for every model still in contention."),
 ("Round 3", "9 Nov", "Only the runs a pick could rest on, on Adlerbot alone."),
 ("Round 4", "9–10 Nov", "One change: the same model reviewed each Python step and sent it back once. It caught none of its misses and broke a finished step, so the review was removed. No Python run finished."),
 ("Round 5", "10 Nov", "Flash-Next's third planning run, the last open question. It failed. Outcome: no local model passed planning or Python; Laguna S passed Swift."),
],
}


def page(title, body):
    return ("<!doctype html><html lang=en><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style><main>{body}</main></html>")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.rename(path)


def tests():
    """(folder, title, what it answers) from tests/README.md's table."""
    for line in (KIT / "tests" / "README.md").read_text().splitlines():
        if m := re.match(r"\|\s*\[([^\]]+)\]\([^)]*\)\s*\|\s*(.*?)\s*\|$", line):
            yield m.group(1), m.group(2)


def kit_pages(folder):
    """The test's files: a page listing them, each as a page, and one .tar.gz of all."""
    out = WWW / folder / "files"   # beside the test's results pages, which this leaves alone
    shutil.rmtree(out, ignore_errors=True)
    files = sorted(p for p in KIT.rglob("*") if p.is_file() and p.name != "COMMIT"
                   and not (p.is_relative_to(KIT / "tests") and not p.is_relative_to(KIT / "tests" / folder)))
    rows = []
    for p in files:
        rel = p.relative_to(KIT).as_posix()
        text = p.read_text(errors="replace")
        write(out / (rel + ".html"), page(rel, f"<p><a href='/tests/{folder}/files/'>← Files</a></p>"
                                                   f"<h1>{html.escape(rel)}</h1><pre>{html.escape(text)}</pre>"))
        rows.append(f"<tr><td><a href='{html.escape(rel)}.html'>{html.escape(rel)}</a></td>"
                    f"<td class=dim>{len(text.splitlines())} lines</td></tr>")
    with tarfile.open(out / f"{folder}.tar.gz", "w:gz") as tar:
        for p in files:
            tar.add(p, arcname=f"{folder}/{p.relative_to(KIT).as_posix()}")
    commit = (KIT / "COMMIT").read_text().strip()
    write(out / "index.html", page(f"{folder} files", f"<p><a href='/tests/'>← All tests</a></p>"
          f"<h1>Files to reproduce {html.escape(folder)}</h1>"
          f"<p class=dim>From the lab repository at {html.escape(commit)}. Start with "
          f"<a href='tests/{folder}/REPRODUCE.md.html'>REPRODUCE.md</a>.</p>"
          f"<p><a href='{folder}.tar.gz'>Download all ({len(files)} files)</a></p>"
          f"<table>{''.join(rows)}</table>"))


def link(url, label):
    return f'<a href="{url}">{label}</a>'


def links(folder):
    """A test's round pages, /tests/<folder>/round<n>/, in round order (a round's other pages are linked from its page)."""
    d = WWW / folder
    rounds = sorted((r for r in d.glob("round*") if re.fullmatch(r"round\d+", r.name) and (r / "index.html").is_file()),
                    key=lambda r: int(r.name[5:]))
    return "<br>".join(link(f"/tests/{folder}/{r.name}/", f"Round&nbsp;{r.name[5:]}") for r in rounds) or "<span class=dim>no results page</span>"


def iterations(folder):
    rows = "".join(f"<tr><td>{n}</td><td class=dim>{d}</td><td>{html.escape(t)}</td></tr>" for n, d, t in ITERATIONS.get(folder, []))
    return f"<h3>Iterations</h3><table>{rows}</table>" if rows else ""


tops, sections = [], []
for folder, about in tests():
    kit = (KIT / "tests" / folder / "REPRODUCE.md").is_file()
    if kit:
        kit_pages(folder)
    results = links(folder)
    files = f'<br><a href="{folder}/files/">Files to reproduce</a>' if kit else ""
    tops.append(f"<tr><td><a href='#{folder}'>{html.escape(folder)}</a></td><td>{results}{files}</td></tr>")
    body = ABOUT.get(folder, f"<p>{html.escape(about)}</p>") + iterations(folder)
    sections.append(f"<section id={folder}><h2>{html.escape(folder)}</h2>{body}</section>")
# Newest test first
tops.reverse()
sections.reverse()
write(WWW / "index.html", page("Lab tests", "<h1>Lab tests</h1>"
      "<table class=top><tr><th>Test</th><th>Links</th></tr>" + "".join(tops) + "</table>"
      "<p class=dim>What each test checks, why it is run this way, and what each iteration changed, below.</p>"
      + "".join(sections)))
print(f"wrote {WWW}/index.html")
