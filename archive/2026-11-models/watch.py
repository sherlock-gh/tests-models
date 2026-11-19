#!/usr/bin/env python3
"""Watches a round's runner log on Sherlock, independent of any session, and starts Claude (Codex
once 10% of Claude's weekly plan is left) unattended (watch-brief.md) on every failure, timeout, machine failure and lane end:
    nohup python3 watch.py <round> >> results/<round>/watch.log 2>&1 &
One Claude at a time, 45 min each (killed at 50); events arriving meanwhile go to the next.
Ends after the lane has ended and Claude has handled its last events."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

T = Path(__file__).resolve().parent
ROUND = sys.argv[1]
RES = T / "results" / ROUND
LOG = Path.home() / "scaffolding/tests-2026-11-models/log.txt"
# A partial score is a model's result, not an event (most steps end in one); a zero, a step with
# no score, a machine failure and a lane's end are, as the test may be at fault (17 Nov: waking on
# every step would have used the owner's weekly Claude plan in a day or two)
EVENT = re.compile(r"\] (?:.* M\d+: (?!pass)(?!.*passed [1-9])|.*(?:machine failure|LANE STOPPED|lane done|lane incomplete|stopped at|STOPPED|fault))")
LIMIT = 50 * 60


def say(msg):
    print(time.strftime("%F %T"), msg, flush=True)


def runner_alive():
    try:
        os.kill(int((RES / "a/runner.lock/pid").read_text()), 0)
        return True
    except (OSError, ValueError):
        return False


def claude_used():
    """(week %, session %) of the owner's Claude plan used, by Claude Code's /usage; None unread"""
    try:
        u = subprocess.run(["claude", "-p", "/usage"], capture_output=True, text=True, timeout=120,
                           stdin=subprocess.DEVNULL).stdout
        return (int(re.search(r"Current week[^:]*:\s*(\d+)% used", u).group(1)),
                int(re.search(r"Current session:\s*(\d+)% used", u).group(1)))
    except (OSError, subprocess.SubprocessError, AttributeError):
        return None


def claude(events):
    prompt = ((T / "watch-brief.md").read_text() + f"\nRound: {ROUND}. Events:\n" + "\n".join(events))
    # Claude until 10% of the week's plan is left (owner, 17 Nov) or the 5-hour session is spent;
    # then Codex, on the owner's ChatGPT plan, does the same work
    used = claude_used()
    codex = used is not None and (used[0] >= 90 or used[1] >= 95)
    who = "codex" if codex else "claude"
    say(f"{who} (Claude used: {used}) on {len(events)} event(s): {events[0][:160]}")
    out = (RES / "watch-claude.log").open("a")
    out.write(f"\n===== {time.strftime('%F %T')} {who}\n")
    out.flush()
    cmd = (["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", prompt] if codex else
           ["claude", "-p", prompt, "--model", "sonnet", "--dangerously-skip-permissions"])
    return subprocess.Popen(cmd, cwd=T,
                            stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                            start_new_session=True), time.time()


def main():
    offset = LOG.stat().st_size
    pending, job, started, dead = [], None, 0, False
    say(f"watching {LOG} for {ROUND}")
    while True:
        with LOG.open(errors="replace") as f:
            f.seek(offset)
            lines = f.read().splitlines()
            offset = f.tell()
        pending += [l for l in lines if EVENT.search(l)]
        if not runner_alive() and not (RES / "a/end").exists() and not dead:
            dead = True
            pending.append(f"{time.strftime('%F %T')} [watch] the runner is not running and the lane has no end marker")
        if runner_alive():
            dead = False
        if job and job.poll() is None and time.time() - started > LIMIT:
            os.killpg(job.pid, 9)
            say("claude killed at its 50-min limit")
        if job and job.poll() is not None:
            job = None
        if pending and not job:
            job, started = claude(pending)
            pending = []
        end = (RES / "a/end").read_text() if (RES / "a/end").exists() else ""
        if end.startswith(("done", "incomplete")) and not runner_alive() and not job and not pending:
            say("the lane ended and its events are handled: done")
            return
        time.sleep(30)


main()
