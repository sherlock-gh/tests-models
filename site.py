"""The tests' home page, on Sherlock: python3 site.py
Writes ~/demo/www/tests/, which Sherlock's demo server shows at http://192.168.50.100:18100/tests/
(the lab network) and pages.sh copies to GitHub Pages. The home page is README.md, rendered: the
repo's front page and the site's are one text. Its links to the Pages site point here instead,
and its links to the repo's files go to GitHub. A round's page is listed by adding its link to
README.md; a round page that README.md doesn't link is reported. For the tests whose files
publish.sh gathered, it also writes the files to reproduce it at /tests/<test>/files/, each
viewable and all in one download. Its input is ~/tests-site/kit/, those files at their paths
under tests/, made by publish.sh, which then runs this. The demo server empties ~/demo/www when
it restarts: run publish.sh again then."""
import html
import re
import shutil
import tarfile
from pathlib import Path

KIT = Path.home() / "tests-site" / "kit"
WWW = Path.home() / "demo" / "www" / "tests"
PAGES = "https://sherlock-gh.github.io/tests-models/"
REPO = "https://github.com/sherlock-gh/tests-models/blob/main/"
STYLE = """:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--dim:#6b6b70;--line:#dcdcd8;--accent:#0b63ce}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--card:#1f1f22;--fg:#ececee;--dim:#9a9aa2;--line:#34343a;--accent:#6aa6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:64rem;margin:0 auto;padding:2rem 1rem 4rem}a{color:var(--accent)}.dim{color:var(--dim)}
table{border-collapse:collapse;width:100%;background:var(--card)}td,th{border:1px solid var(--line);padding:.5rem .7rem;text-align:left;vertical-align:top}
pre{background:var(--card);border:1px solid var(--line);padding:1rem;border-radius:.4rem;overflow-x:auto;font-size:.85rem}
section{background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:1.2rem 1.4rem;margin:0 0 1.5rem}
section h2{margin:0 0 .6rem;font-size:1.3rem}
h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin:1.4rem 0 .5rem}
section table td:first-child{white-space:nowrap;font-weight:600}section ul{margin:0;padding-left:1.2rem}section li{margin:.25rem 0}
table.top{margin:0 0 .6rem}"""


def page(title, body):
    return ("<!doctype html><html lang=en><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style><main>{body}</main></html>")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.rename(path)


def href(url):
    """Pages links stay on this site; the repo's files go to GitHub."""
    if url.startswith(PAGES):
        return "/tests/" + url[len(PAGES):]
    if url.startswith(("#", "http://", "https://", "/")):
        return url
    return REPO + url


def inline(text):
    s = html.escape(text, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{html.escape(href(m.group(2)))}">{m.group(1)}</a>', s)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md):
    """README.md as HTML: the Markdown it uses (headings, paragraphs, tables, lists, code, bold,
    links), each ## heading opening a section."""
    out, open_section = [], False
    for block in re.split(r"\n\s*\n", md.strip()):
        lines = block.splitlines()
        first = lines[0]
        if m := re.match(r"(#{1,3}) (.*)", first):
            level, text = len(m.group(1)), m.group(2)
            if level == 2:
                out.append("</section>" if open_section else "")
                out.append(f"<section id={re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-'))}>")
                open_section = True
            out.append(f"<h{level}>{inline(text)}</h{level}>")
            lines = lines[1:]
            if not lines:
                continue
            first = lines[0]
        if first.startswith("|"):
            head, rows = cells(lines[0]), [cells(l) for l in lines[2:]]
            cls = "" if open_section else " class=top"
            out.append(f"<table{cls}><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>")
        elif first.startswith("- "):
            out.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in lines) + "</ul>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    if open_section:
        out.append("</section>")
    return "".join(out)


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


for reproduce in (KIT / "tests").glob("*/REPRODUCE.md"):
    kit_pages(reproduce.parent.name)
readme = (KIT / "tests" / "README.md").read_text()
write(WWW / "index.html", page("Lab tests", render(readme)))
print(f"wrote {WWW}/index.html")
for r in sorted(WWW.glob("*/round*/index.html")):
    url = f"{PAGES}{r.parent.parent.name}/{r.parent.name}/"
    if url not in readme:
        print(f"not linked from README.md: {url}")
