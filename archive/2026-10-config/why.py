"""Why a milestone ended as it did, written by the runner on Sherlock when one doesn't pass:
python3 why.py <label> <repo> <prompt-file> <start> <end> <outcome> <note>
Writes the lane's why/<label>.md (TEST_WHY) (an earlier file of the same label is kept as
<label>.<time>.md), answering "what did the agent and the model actually do": the runner's
30-s watch, how Hermes's turn ended (its usage file), Hermes's session turn by turn (each tool
call, its exit code, repeats), the check's output, the repo's git state.
Client content stays out: the briefs and everything written from them are read only through
blind sets. So the file keeps tool names, paths, sizes, exit codes and times, and nothing a
model or a command wrote: a shell command shows as its program (and subcommand) with a short
fingerprint, so the same command repeated is visible (test 2's are shown whole: no client
content); output and the model's prose show only
as sizes; commits by hash. why/ stays on Sherlock and never reaches the repo. Prints one line
for the Telegram note: how Hermes's turn ended and the most repeated call.
Exits nonzero only if it could not write the file."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

label, repo, prompt_file, start, end, outcome, note = sys.argv[1:8]
start, end = float(start), float(end)
HOME = Path.home()
USAGE = Path(os.environ["TEST_USAGE"])          # the lane's (lib.sh)
OUT = Path(os.environ["TEST_WHY"])
HERMES = HOME / ".hermes"


def clip(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n] + f" … [{len(s)} chars]"


def hms(ts):
    return datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")


def usage():
    try:
        return json.loads((USAGE / f"{label}.json").read_text())
    except (OSError, ValueError):
        return {}


def session(sid):
    """(session id, rows, problem) of this job's Hermes session."""
    try:
        con = sqlite3.connect(f"file:{HERMES / 'state.db'}?mode=ro", uri=True)
        if not sid:   # a job ended by the runner writes no usage file: find it by its prompt
            try:
                prompt = Path(prompt_file).read_text().strip()
            except OSError as e:
                return None, [], f"no usage file, and the prompt is unreadable: {e}"
            for s, content in con.execute(
                    "select session_id, content from messages where role='user' and timestamp >= ? "
                    "and timestamp <= ? order by timestamp", (start - 5, end + 5)):
                if (content or "").strip() == prompt:
                    sid = s
                    break
        if not sid:
            return None, [], "no session with this job's prompt in its time"
        rows = con.execute("select role, content, tool_calls, tool_name, finish_reason, timestamp "
                           "from messages where session_id=? order by id", (sid,)).fetchall()
        return sid, rows, ""
    except sqlite3.Error as e:
        return sid, [], f"Hermes's database unreadable: {e}"


def command_shape(cmd):
    """A shell command's program (and, for git and the build tools, its subcommand), and a
    fingerprint of the whole: arguments can carry client text, so none is shown."""
    words = cmd.split()
    shown = words[:1] if words and re.fullmatch(r"[a-z][a-z0-9_.-]{0,19}", words[0]) else []
    if shown and shown[0] in ("git", "swift", "python", "python3", "pip", "pytest", "uv") and len(words) > 1 \
            and re.fullmatch(r"-?[a-z][a-z-]{0,15}", words[1]):
        shown.append(words[1])
    return f"{' '.join(shown) or '?'} #{hashlib.sha1(cmd.encode()).hexdigest()[:6]} [{len(cmd)} chars]"


def call_text(c):
    f = c.get("function") or {}
    name = f.get("name", "?")
    try:
        args = json.loads(f.get("arguments") or "{}")
    except ValueError:
        return f"{name} [unparsed arguments]"
    if not isinstance(args, dict):
        return f"{name} [arguments]"
    shown = []
    for k, v in args.items():
        if k in ("command", "cmd"):
            shown.append(f"{k}: {clip(v, 200) if label.startswith('test2-') else command_shape(str(v))}")
        elif k in ("path", "file_path", "paths", "cwd", "workdir", "url") or isinstance(v, (int, float, bool)):
            shown.append(f"{k}: {clip(v, 120)}")
        else:
            shown.append(f"{k}: [{len(str(v))} chars]")
    return f"{name} {{{', '.join(shown)}}}"


def tool_result(content):
    try:
        d = json.loads(content or "")
    except ValueError:
        return f"[{len(content or '')} chars]"
    if not isinstance(d, dict):
        return f"[{len(content or '')} chars]"
    if "output" not in d and "exit_code" not in d:   # a file read or similar: size only
        return (f"[{d.get('total_lines', '?')} lines, {d.get('file_size', '?')} bytes"
                f"{', NOT FOUND' if d.get('not_found') else ''}{', error' if d.get('error') else ''}]")
    return (f"exit {d.get('exit_code')}, {len(str(d.get('output') or '').splitlines())} lines out"
            f"{', the tool reported an error' if d.get('error') else ''}")


def git(*a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


u = usage()
sid, rows, problem = session(u.get("session_id"))
turn = ", ".join(f"{k} {u[k]}" for k in ("completed", "failed", "interrupted", "partial", "turn_exit_reason", "api_calls")
                 if k in u)
lines = [f"# {label}: {outcome}", "",
         f"- Job: {hms(start)} to {hms(end)} ({int(end - start)} s); runner's note: {clip(note, 300) or '-'}",
         f"- Hermes's turn: {turn or 'no usage file (Hermes was stopped, or crashed)'}",
         f"- Hermes session: {sid or 'not found'}{f' ({problem})' if problem else ''}", ""]

final_ts = last_ts = None
calls = {}
if rows:
    lines += ["## The session, turn by turn", ""]
    for role, content, tool_calls, tool_name, finish, ts in rows:
        if role == "user":
            lines.append(f"- {hms(ts)} **prompt** [{len(content or '')} chars]")
        elif role == "assistant":
            if (content or "").strip():
                final_ts = ts
                lines.append(f"- {hms(ts)} **model writes** ({finish or '-'}) [{len(content.strip())} chars]")
            try:
                tcs = json.loads(tool_calls or "[]")
            except ValueError:
                tcs = []
            for c in tcs:
                t = call_text(c)
                calls[t] = calls.get(t, 0) + 1
                lines.append(f"- {hms(ts)} **call** {t}" + (f"  ← the same call, time {calls[t]}" if calls[t] > 1 else ""))
        elif role == "tool":
            lines.append(f"  - {hms(ts)} result ({tool_name or '?'}): {tool_result(content)}")
        last_ts = ts
    lines += ["", "## Summary", "",
              f"- Model turns {sum(1 for r in rows if r[0] == 'assistant')}, tool calls {sum(calls.values())}, "
              f"distinct calls {len(calls)}"]
    lines += [f"- The same call {n} times: {t}" for t, n in calls.items() if n > 2]
    lines.append("- The session's last entry: " + ("the model writing text" if final_ts is not None and final_ts == last_ts
                                                    else "a tool call or its result (stopped mid-work)"))

for f, title in ((USAGE / f"{label}.trace", "The runner's watch (one line each 30 s), last 60 lines"),
                 (USAGE / f"{label}.check", "The check's output, last 60 lines"),
                 (USAGE / f"{label}.check-err", "The check's errors, last 60 lines")):
    try:
        text = f.read_text().splitlines()
    except OSError:
        continue
    if text:   # the first line (the job's start) and the last 59
        lines += ["", f"## {title}", "", "```", *(text[:1] + (["…"] if len(text) > 60 else []) + text[1:][-59:]), "```"]

lines += ["", "## The repo", "", "```",
          "branch: " + git("branch", "--show-current"),
          git("log", "--all", "--graph", "--format=%h %cr", "-15"),
          "uncommitted: " + (", ".join(l[3:] for l in git("status", "--porcelain").splitlines()) or "none"), "```"]
served = Path(os.environ["TEST_RES"]) / "served"
lines += ["", "## The server", "",
          f"- Sherlock's record of the model served: {served.read_text().strip() if served.exists() else '(none)'}"]

OUT.mkdir(parents=True, exist_ok=True)
dest = OUT / f"{label}.md"
if dest.exists():   # a label redone after a restart: keep the earlier explanation
    dest.rename(OUT / f"{label}.{time.strftime('%Y%m%d-%H%M%S', time.localtime(dest.stat().st_mtime))}.md")
dest.write_text("\n".join(lines) + "\n")
summary = [f"Hermes: {u.get('turn_exit_reason') or ('turn failed' if u.get('failed') else 'no usage file')}"]
if calls:
    t, n = max(calls.items(), key=lambda x: x[1])
    if n > 2:
        summary.append(f"the same call {n} times: {t}")
if problem:
    summary.append(problem)
print("; ".join(summary))
