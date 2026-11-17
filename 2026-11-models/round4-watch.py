#!/usr/bin/env python3
"""Persistent round-4 heartbeat and event-driven Hermes coordinator handoff."""
import datetime
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent
STATUS = Path('/private/tmp/hermes-round4-operations-status.txt')
SETUP = Path('/Users/sherlock/workspaces/tests/2026-11-models/setup-flash-r4')
LOG = Path('/Users/sherlock/scaffolding/tests-2026-11-models/log.txt')
PROMPT = Path('/private/tmp/hermes-round4-coordinator-brief.txt')
COORDINATOR = Path('/private/tmp/hermes-round4-coordinator.log')
HERMES = '/Users/sherlock/.local/bin/hermes'
INITIAL_COORDINATOR = 73828
SETUP_PID = 70183
SETUP_DEADLINE = datetime.datetime(2026, 11, 17, 2, tzinfo=datetime.timezone(datetime.timedelta(hours=-8)))
EVENT = re.compile(r'\b(?:fail|timeout|machine.failure|LANE STOPPED|lane done|lane incomplete|fault)\b', re.I)


def live(pid):
    if not pid:
        return False
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
        if waited:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def note(message):
    stamp = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    with STATUS.open('a') as out:
        out.write(f'{stamp} watcher PID {os.getpid()} {message}\n')


def launch(reason):
    with COORDINATOR.open('a') as out:
        agent = subprocess.Popen(
            [HERMES, '--provider', 'openai-codex', '-m', 'gpt-6-sol', '-z',
             PROMPT.read_text() + '\nWake reason: ' + reason],
            cwd=ROOT.parent, stdin=subprocess.DEVNULL, stdout=out,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    note(f'coordinator PID {agent.pid} spawned: {reason[:220]}')
    return agent.pid


def new_log(offset):
    try:
        with LOG.open(errors='replace') as source:
            source.seek(offset)
            text = source.read()
            return source.tell(), [line for line in text.splitlines()
                                   if 'round4' in line or EVENT.search(line)]
    except FileNotFoundError:
        return offset, []


def main():
    coordinator = INITIAL_COORDINATOR
    offset = LOG.stat().st_size if LOG.exists() else 0
    setup_seen = not live(SETUP_PID)
    deadline_seen = False
    last_launch = None
    rapid_exits = 0
    cooldown_until = 0
    pending = []
    dead_seen = False
    note(f'start; coordinator {coordinator}; setup {SETUP_PID} live={not setup_seen}; '
         'setup deadline 02:00 PST; round <=7d; idle 2h+30m; check 15m; load 20m')
    while True:
        now = datetime.datetime.now().astimezone()
        setup_live = live(SETUP_PID)
        offset, events = new_log(offset)
        if not setup_live and not setup_seen:
            events.append('setup exited; inspect notes, amendments, kit, validation')
            setup_seen = True
        if setup_live and now >= SETUP_DEADLINE and not deadline_seen:
            events.append('setup reached 02:00 PST deadline; diagnose without duplicate setup')
            deadline_seen = True
        for event in events:
            note(f'event: {event[:500]}')
            pending.append(event)
        alive = live(coordinator)
        if not alive and not dead_seen:
            dead_seen = True
            if last_launch is None:
                pending.append('initial coordinator exited; inspect state and unreviewed why files')
            elif time.monotonic() - last_launch < 180:
                rapid_exits += 1
                cooldown_until = time.monotonic() + min(7200, 300 * 2 ** min(rapid_exits, 4))
                pending.append('coordinator exited quickly; inspect coordinator log and unreviewed why files')
                note(f'BLOCKER: coordinator {coordinator} exited quickly; retry after '
                     f'{int(cooldown_until - time.monotonic())}s; inspect {COORDINATOR}')
            else:
                rapid_exits = 0
        results = ROOT / 'results/round4'
        end = results / 'a/end'
        outcome = end.read_text().strip() if end.exists() else None
        finished = ((results / 'validated-flash-r4').exists()
                    and outcome in ('done', "incomplete: the round's 7-day limit came first")
                    and not (results / 'a/runner.lock').exists())
        if finished and not alive:
            note(f'finished: validated flash-r4, lane a ended {outcome}; watcher stops')
            break
        if not alive and pending and time.monotonic() >= cooldown_until:
            coordinator = launch('; '.join(pending[-5:]))
            pending.clear()
            last_launch = time.monotonic()
            dead_seen = False
        notes = (SETUP / 'SETUP-NOTES.md').exists() or (SETUP / 'harness/plans/flash-r4/SETUP-NOTES.md').exists()
        note(f'tick coordinator={coordinator} live={live(coordinator)} pending={len(pending)} '
             f'retry_seconds={max(0, int(cooldown_until - time.monotonic()))} setup={setup_live} '
             f'notes={notes} log_offset={offset}; '
             'limits setup 02:00 PST, round 7d, idle 2h+30m, check 15m, load 20m')
        time.sleep(45)


if __name__ == '__main__':
    main()
