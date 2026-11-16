"""Hidden tests for the back office (Terra's plan): each test starts the build's server
(`python3 backoffice/server.py --data PATH --port N`, from TARGET, the repo) on a fresh data
file, and talks to it over HTTP (plan contracts/exact-interfaces.md), setting the clock with X-Clock.
Monday 2026-11-16 is the first test day."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

TARGET = Path(os.environ["TARGET"])
MON, TUE, WED, SAT, SUN = "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-21", "2026-11-22"
BEFORE = "2026-11-13T12:00:00"   # "now" for removals: before every test job
NEXT_MON = "2026-11-23"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App:
    def __init__(self, data):
        self.data = data
        self.proc = None
        self.start()

    def start(self):
        self.port = free_port()
        self.log = open(self.data.with_suffix(".log"), "ab")
        self.proc = subprocess.Popen([sys.executable, "backoffice/server.py", "--data", str(self.data), "--port", str(self.port)],
                                     cwd=TARGET, stdout=self.log, stderr=self.log)
        for _ in range(100):
            if self.proc.poll() is not None:
                pytest.fail(f"the server exited at start: {self.data.with_suffix('.log').read_text()[-800:]}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        pytest.fail("the server did not listen within 10 s")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()

    def restart(self):
        self.stop()
        self.start()

    def call(self, method, path, body=None, at=None):
        """(status, parsed body or None); `at`, an instant, sets the clock for the request"""
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if at:
            headers["X-Clock"] = at
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            return status, json.loads(raw) if raw.strip() else None
        except ValueError:
            return status, raw.decode(errors="replace")

    def ok(self, method, path, body=None, at=None):
        status, out = self.call(method, path, body, at)
        assert 200 <= status < 300, f"{method} {path} {body}: {status} {out}"
        return out

    def fails(self, method, path, body=None, code=None, status=None, at=None):
        """The request fails with the error body; the server still answers afterwards."""
        st, out = self.call(method, path, body, at)
        assert 400 <= st < 500, f"{method} {path} {body}: expected an error, got {st} {out}"
        assert isinstance(out, dict) and "error" in out and "code" in out["error"] and "message" in out["error"], out
        if code:   # one code, or any of several where the plan doesn't say which
            assert out["error"]["code"] in ((code,) if isinstance(code, str) else code), out
        if status:
            assert st == status, (st, out)
        assert self.call("GET", "/api/cleaners")[0] == 200, "the server stopped answering after an error"
        return out

    # helpers
    def cleaners(self, n):
        return [self.ok("POST", "/api/cleaners", {"name": f"Cleaner {i}"})["id"] for i in range(n)]

    def client(self, name="Client A"):
        return self.ok("POST", "/api/clients", {"name": name})["id"]

    def book(self, client, needed, length, day):
        return self.ok("POST", "/api/jobs", {"clientId": client, "cleanersNeeded": needed, "durationMinutes": length, "requestedDate": day})

    def arrive(self, job, cleaner, at):
        return self.ok("POST", f"/api/jobs/{job}/arrive", {"cleanerId": cleaner}, at=at)

    def depart(self, job, cleaner, at):
        return self.ok("POST", f"/api/jobs/{job}/depart", {"cleanerId": cleaner}, at=at)

    def state(self, invoices=False):
        paths = ["/api/cleaners", "/api/clients", "/api/jobs"] + (["/api/invoices"] if invoices else [])
        return [self.ok("GET", p) for p in paths]


def by_id(xs):
    return {x["id"]: x for x in xs}


def assert_no_overlaps(jobs):
    """The plan's invariant: per cleaner and date, live jobs at least 60 min apart; booked jobs
    within 8:00-17:00 on a weekday (an extended end may pass 17:00)."""
    from datetime import date
    live = [j for j in jobs if j["status"] != "cancelled"]
    for j in live:
        assert date.fromisoformat(j["date"]).weekday() < 5, j
        assert j["startMinute"] >= 480, j
        assert len(set(j["cleanerIds"])) == j["cleanersNeeded"] == len(j["cleanerIds"]), j
    per = {}
    for j in live:
        for c in j["cleanerIds"]:
            per.setdefault((c, j["date"]), []).append(j)
    for k, js in per.items():
        js.sort(key=lambda j: j["startMinute"])
        for a, b in zip(js, js[1:]):
            assert b["startMinute"] >= a["endMinute"] + 60, f"cleaner {k[0]} on {k[1]}: {a} then {b}"


@pytest.fixture
def app(tmp_path):
    a = App(tmp_path / "data.json")
    yield a
    a.stop()
