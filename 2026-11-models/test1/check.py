"""Test 1's completion check, run on Sherlock: python3 check.py <repo> <step>
Passes when the step's file is committed, has every section its template requires, each with
something in it, and none of the template's placeholders left. [NEEDS CLARIFICATION] markers
are allowed: the steps write them on purpose. The template's own HTML comments (guidance the
reader never sees) are removed before checking (round 3: round 2 failed a filled spec on them),
and a line that is all bold ("**Options**") counts as a section title as a heading does (round 3:
round 2 failed a concept with every option written under one). Placeholders a writer leaves for
a person to fill ("[Your Name]", "[Client]", "[Date]") count as placeholders (round 3: round 2's
check let one through); a route's "<name>" and a field's "[date picker]" don't (round 3 failed
Flash-Next on them).
Required sections: the spec template's sections marked mandatory; for plan and tasks, the
sections their skills say to fill (speckit-plan step 3, speckit-tasks step 4). The estimate
(estimate.md, as its prompt describes it): a Desktop and a Mobile section, each with a number of
human hours and a number of tokens.
Exit 0: complete; 1: the work falls short (the note says where); 3: the check itself failed."""
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path


def crashed(*exc):   # a fault in the check is not the model's: exit 3, which stops the round
    traceback.print_exception(*exc)
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(3)


sys.excepthook = crashed

repo, step = Path(sys.argv[1]), sys.argv[2]

SECTIONS = {
    "specify": ["User Scenarios & Testing", "Requirements", "Success Criteria"],
    "plan": ["Summary", "Technical Context", "Constitution Check", "Project Structure"],
    "tasks": ["Setup", "Foundational", "Dependencies", "Implementation Strategy"],
    "estimate": ["Desktop", "Mobile"],
}
PLACEHOLDER = re.compile(r"<(short title|ISO 8601 date|ASSESS_SLUG|sanitized URL[^>]*|One or two neutral sentences\.?|who / \[NEEDS CLARIFICATION\]|what prompted it[^>]*)>"
                         r"|\[(FEATURE NAME|FEATURE|DATE|###-feature-name|Brief Title|Title|REMOVE IF UNUSED|link)\]"
                         r"|ACTION REQUIRED|new-capability \| improvement \| fix"
                         # left for a person to fill in (not a link: "[text](url)")
                         r"|(?i:\[(?:Your|Insert|TBD|TODO|Placeholder)\b[^\]\n]{0,40}\])(?!\()"
                         # "[Client]", "[Date]", "[Company Name]", but not text that starts with
                         # the word: "[date picker]" names a form field (round 3: it failed Flash-Next)
                         r"|(?i:\[(?:Client|Company|Name|Date)(?: name)?\])(?!\()")
COMMENT = re.compile(r"<!--.*?-->", re.S)
BOLD_TITLE = re.compile(r"\s*(?:\*\*|__)([^*_\n]+?)(?:\*\*|__)\s*:?\s*$")


# "Human hours: 120", "**Tokens:** ~2,500,000", "Tokens: 2.5M": a number after the label
NUMBER = {"human hours": re.compile(r"(?im)^\W*human hours\W*:\W*~?\s*\d"),
          "tokens": re.compile(r"(?im)^\W*tokens\W*:\W*~?\s*\d")}


def target():
    if step == "estimate":
        return repo / "estimate.md"
    try:
        feature = json.loads((repo / ".specify/feature.json").read_text())["feature_directory"]
    except (OSError, ValueError, KeyError):
        return None
    name = {"specify": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}[step]
    # the prompts say "the feature folder under specs/ named in .specify/feature.json": a name
    # without specs/ reads it that way too (17 Nov: Devstral's runs 1 and 3, failed on it)
    if not (repo / feature / name).is_file() and (repo / "specs" / feature / name).is_file():
        return repo / "specs" / feature / name
    return repo / feature / name


def fail(why):
    print(why)
    sys.exit(1)


f = target()
if f is None or not f.is_file():
    looked = [f] if f else [repo / ".specify/feature.json"]
    fail(f"no {step} file (looked for {', '.join(str(p.relative_to(repo)) for p in looked)})")
rel = str(f.relative_to(repo))
if subprocess.run(["git", "-C", str(repo), "diff", "--quiet", "HEAD", "--", rel]).returncode or \
        subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{rel}"], capture_output=True).returncode:
    fail(f"{rel} not committed as it stands")
text = COMMENT.sub("", f.read_text(errors="replace"))
if not text.strip():
    fail(f"{rel} is empty")
if m := PLACEHOLDER.search(text):
    fail(f"{rel}: placeholder left: {m.group(0)}")

# Sections: a heading containing the name; its body runs to the next heading of the same or a
# higher level, and must hold something. A line that is all bold is a title one level below the
# heading it sits under.
lines = text.splitlines()
heads, level = [], 0
for i, l in enumerate(lines):
    if m := re.match(r"(#{1,6})\s+(.*)", l):
        level = len(m.group(1)); heads.append((i, level, m.group(2)))
    elif b := BOLD_TITLE.fullmatch(l):
        heads.append((i, level + 1, b.group(1)))
for name in SECTIONS[step]:
    hit = next(((i, lvl) for i, lvl, t in heads if name.lower() in t.lower()), None)
    if hit is None:
        fail(f"{rel}: section missing: {name}")
    i, lvl = hit
    end = next((j for j, l2, _ in heads if j > i and l2 <= lvl), len(lines))
    body = "\n".join(lines[i + 1:end])
    if not body.strip():
        fail(f"{rel}: section empty: {name}")
    if step == "estimate":
        for label, rx in NUMBER.items():
            if not rx.search(body):
                fail(f"{rel}: {name} has no {label} figure")
if step == "estimate":   # the open questions, with the answers assumed (test1.sh's prompt): committed, maybe empty
    q = "questions.md"
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{q}"], capture_output=True).returncode:
        fail(f"{q} not committed")
print(f"{rel} complete")
