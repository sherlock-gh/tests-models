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
    pending = []
    dead_seen = False
    recent_event = 'none'
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
            recent_event = event[:140]
            note(f'event: {event[:500]}')
            match = re.search(r'why/([\w.-]+\.md)', event)
            if match:
                why = ROOT / 'results/round4/a/why' / match.group(1)
                try:
                    evidence = why.read_text(errors='replace')
                    note(f'why read whole: {why.name}, {len(evidence)} characters; '
                         'classification pending coordinator')
                except OSError as error:
                    note(f'BLOCKER: cannot read why file {why}: {error}')
            pending.append(event)
        alive = live(coordinator)
        if not alive and not dead_seen:
            dead_seen = True
            note(f'coordinator {coordinator} exited; awaiting a runner event')
        results = ROOT / 'results/round4'
        end = results / 'a/end'
        outcome = end.read_text().strip() if end.exists() else None
        finished = ((results / 'validated-flash-r4').exists()
                    and outcome in ('done', "incomplete: the round's 7-day limit came first")
                    and not (results / 'a/runner.lock').exists())
        if finished and not alive:
            note(f'finished: validated flash-r4, lane a ended {outcome}; watcher stops')
            break
        if not alive and pending:
            coordinator = launch('; '.join(pending[-5:]))
            pending.clear()
            dead_seen = False
        notes = (SETUP / 'SETUP-NOTES.md').exists() or (SETUP / 'harness/plans/flash-r4/SETUP-NOTES.md').exists()
        lock = results / 'a/runner.lock/pid'
        try:
            runner = int(lock.read_text().strip())
        except (OSError, ValueError):
            runner = 0
        current = results / 'a/now'
        phase = current.read_text().strip() if current.exists() else 'not recorded'
        note(f'tick phase={phase[:100]} coordinator={coordinator} live={live(coordinator)} '
             f'runner={runner} live={live(runner)} pending={len(pending)} '
             f'setup={setup_live} notes={notes} log_offset={offset} evidence={recent_event!r} '
             'blockers=none; deadline 2026-11-23 23:46:37 PST + grace; '
             'limits idle 2h+30m, check 15m, load 20m')
        time.sleep(45)


if __name__ == '__main__':
    main()
