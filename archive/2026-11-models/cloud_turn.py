"""One Claude Code or Codex turn, read for cloud.sh (README, "Cloud comparison").

  cloud_turn.py parse <claude|codex> <stream> <out.json> <reply.txt> <limits.json> <agent version>
      The turn's result: completed, failed, model calls, the model, tokens, and the plan's 5-hour
      and weekly use ("five", "week": percent used and when the window resets) and whether a
      limit cut it off ("limited", "resets"). The last message goes to reply.txt; the plan's use,
      when the turn reported it, to limits.json.
  cloud_turn.py week <limits.json>
      "<percent> <resets>" for the weekly window, or nothing when no turn has reported it.
  cloud_turn.py why <claude|codex> <label> <repo> <outcome> <note> <usage dir> <why dir>
      why/<label>.md, as why.py writes Hermes's: tool names, counts, times and commit hashes,
      nothing a model or a command wrote. Prints its one-line summary.

Claude Code reports the plan's use in its stream (rate_limit_event); Codex in its session record
under ~/.codex/sessions (token_count), which also names the model it ran.
"""
import collections
import json
import subprocess
import sys
import time
from pathlib import Path


def events(path):
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def window(used, resets):
    return {"used": round(used, 1), "resets": int(resets)} if used is not None and resets else None


def parse_claude(es):
    init, res, wins, limited, resets = {}, None, {}, False, None
    for e in es:
        if e.get("type") == "system" and e.get("subtype") == "init":
            init = e
        elif e.get("type") == "result":
            res = e
        elif e.get("type") == "rate_limit_event":
            info = e.get("rate_limit_info") or {}
            wins.update(info.get("unifiedWindows") or {})
            if info.get("status") == "rejected":
                limited, resets = True, info.get("resetsAt")
    r = res or {}
    five, week = wins.get("five_hour") or {}, wins.get("seven_day") or {}
    return {"completed": bool(res) and r.get("subtype") == "success" and not r.get("is_error"),
            "failed": bool(r.get("is_error")), "api_calls": r.get("num_turns", 0), "model": init.get("model", ""),
            "subtype": r.get("subtype", ""), "duration_ms": r.get("duration_ms"), "cost_usd": r.get("total_cost_usd"),
            "usage": r.get("usage"), "model_usage": r.get("modelUsage"),
            "five": window(five.get("utilization", 0) * 100 if five else None, five.get("resetsAt")),
            "week": window(week.get("utilization", 0) * 100 if week else None, week.get("resetsAt")),
            "limited": limited, "resets": resets}, r.get("result") if isinstance(r.get("result"), str) else ""


def parse_codex(es):
    thread, usage, completed, failed, errors, said = "", collections.Counter(), False, False, [], ""
    for e in es:
        t = e.get("type")
        if t == "thread.started":
            thread = e.get("thread_id", "")
        elif t == "turn.completed":
            completed = True
            usage.update({k: v for k, v in (e.get("usage") or {}).items() if isinstance(v, int)})
        elif t == "turn.failed":
            failed = True
            errors.append(str((e.get("error") or {}).get("message", "")))
        elif t == "error":
            errors.append(str(e.get("message", "")))
        elif t == "item.completed" and (e.get("item") or {}).get("type") == "agent_message":
            said = e["item"].get("text", "")
    model, calls, rl = "", 0, {}
    files = sorted((Path.home() / ".codex/sessions").glob(f"*/*/*/*{thread}.jsonl")) if thread else []
    for r in events(files[-1]) if files else []:
        p = r.get("payload") or {}
        if r.get("type") == "turn_context":
            model = p.get("model") or model
        elif p.get("type") == "token_count":
            calls += 1
            rl = p.get("rate_limits") or rl
    five, week = rl.get("primary") or {}, rl.get("secondary") or {}
    full = [w for w in (five, week) if (w.get("used_percent") or 0) >= 100]
    limited = bool(rl.get("rate_limit_reached_type")) or bool(full) or any("limit" in m.lower() for m in errors)
    resets = (full or [five])[0].get("resets_at") if limited else None
    return {"completed": completed and not failed, "failed": failed or (bool(errors) and not completed),
            "api_calls": calls or int(completed), "model": model, "subtype": "failed" if failed else "completed" if completed else "",
            "duration_ms": None, "cost_usd": None, "usage": dict(usage) or None, "model_usage": None,
            "five": window(five.get("used_percent"), five.get("resets_at")),
            "week": window(week.get("used_percent"), week.get("resets_at")),
            "limited": limited, "resets": resets}, said


def parse(agent, stream, out, reply, limits, version):
    res, said = (parse_claude if agent == "claude" else parse_codex)(events(stream))
    res["agent_version"] = version
    Path(out).write_text(json.dumps(res))
    if said:
        with open(reply, "a") as f:
            f.write(said.rstrip() + "\n")
    if res["week"] or res["five"]:
        Path(limits).write_text(json.dumps({"five": res["five"], "week": res["week"], "at": int(time.time())}))


def week(limits):
    try:
        w = json.loads(Path(limits).read_text()).get("week")
    except (OSError, ValueError):
        return
    if w:
        print(int(w["used"]), w["resets"])


def why(agent, label, repo, outcome, note, usage, out):
    u, w = Path(usage), Path(out)
    read = lambda p: p.read_text(errors="replace") if p.exists() else ""
    try:
        res = json.loads(read(u / f"{label}.json") or "{}")
    except ValueError:
        res = {}
    tools, failed = collections.Counter(), 0
    for e in events(u / f"{label}.stream"):
        if agent == "claude":
            for c in (e.get("message") or {}).get("content") or [] if e.get("type") in ("assistant", "user") else []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    tools[c.get("name", "?")] += 1
                elif isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                    failed += 1
        elif e.get("type") == "item.completed":
            i = e.get("item") or {}
            if i.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                tools[i["type"]] += 1
                failed += i.get("status") == "failed" or i.get("exit_code") not in (None, 0)
    name = "Claude Code" if agent == "claude" else "Codex"
    ended = f"{res.get('subtype') or 'no result'}, {res.get('api_calls', 0)} model calls" if res else "no result: ended by the runner"
    calls = ", ".join(f"{n} x{k}" for n, k in tools.most_common()) or "none"
    summary = f"{name}: {ended}; tool calls {calls}; {failed} failed"
    waits = sorted(u.glob(f"{label}.w*.json"))
    if waits:
        summary += f"; redone after {len(waits)} usage limit{'s' * (len(waits) > 1)}"
    git = subprocess.run(["git", "-C", repo, "log", "--format=%h %cr", "-5"], capture_output=True, text=True).stdout
    w.mkdir(parents=True, exist_ok=True)
    f = w / f"{label}.md"
    if f.exists():
        f.rename(w / f"{label}.{int(f.stat().st_mtime)}.md")
    end = {k: res.get(k) for k in ("subtype", "api_calls", "model", "duration_ms", "five", "week", "limited")}
    f.write_text(f"# {label}: {outcome}\n\n{note}\n\n{summary}\n\n## The runner's watch\n\n{read(u / f'{label}.trace')}\n"
                 f"## How the turn ended\n\n{json.dumps(end)}\n\n## The check\n\n{read(u / f'{label}.check')}"
                 f"{read(u / f'{label}.check-err')}\n## Commits, newest first\n\n{git}")
    print(summary)


if __name__ == "__main__":
    {"parse": parse, "week": week, "why": why}[sys.argv[1]](*sys.argv[2:])
