"""Hidden tests for the back office (Flash-Next's plan): each test starts the build's app
(`webapp/app.py`, from TARGET, the repo, with its .venv's Python if it has one) on a fresh STORE
file and a free PORT, and drives its routes as the plan's forms do, asking for JSON answers
(plan contracts/exact-interfaces.md). Monday 2027-11-15 is the first test day."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest

TARGET = Path(os.environ["TARGET"])
MON, TUE, FRI, SAT, NEXT_MON = "2027-11-15", "2027-11-16", "2027-11-19", "2027-11-20", "2027-11-22"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App:
    def __init__(self, store):
        self.store = store
        self.start()

    def start(self):
        self.port = free_port()
        py = TARGET / ".venv" / "bin" / "python"
        self.log = open(self.store.with_suffix(".log"), "ab")
        self.proc = subprocess.Popen([str(py) if py.exists() else sys.executable, "webapp/app.py"], cwd=TARGET,
                                     env={**os.environ, "PORT": str(self.port), "STORE": str(self.store)},
                                     stdout=self.log, stderr=self.log)
        for _ in range(150):
            if self.proc.poll() is not None:
                pytest.fail(f"the app exited at start: {self.store.with_suffix('.log').read_text()[-800:]}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        pytest.fail("the app did not listen within 15 s")

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()

    def restart(self):
        self.stop()
        self.start()

    def call(self, method, path, form=None, json_answer=True):
        data = None if form is None else urllib.parse.urlencode(form).encode()
        headers = {"Accept": "application/json"} if json_answer else {}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        if not json_answer:
            return status, raw.decode(errors="replace")
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw.decode(errors="replace")

    def ok(self, method, path, form=None):
        st, out = self.call(method, path, form)
        assert st == 200 and not (isinstance(out, dict) and "error" in out), f"{method} {path} {form}: {st} {out}"
        return out

    def get(self, path):
        return self.ok("GET", path)

    def post(self, path, form=None):
        return self.ok("POST", path, form or {})

    def fails(self, method, path, form=None, codes=()):
        """An error answer (200 with {"error": {code, message}}, the plan's error rule), with one of
        `codes` where the plan says which; the app keeps answering."""
        st, out = self.call(method, path, form if form is not None else ({} if method == "POST" else None))
        assert isinstance(out, dict) and "error" in out, f"{method} {path} {form}: expected an error, got {st} {out}"
        assert out["error"].get("message"), out
        if codes:
            assert out["error"]["code"] in codes, out
        assert self.call("GET", "/cleaners")[0] == 200, "the app stopped answering after an error"
        return out

    # helpers
    def cleaners(self, n):
        return sorted(self.post("/cleaners", {"name": f"Cleaner {i}"})["id"] for i in range(n))

    def client(self, name="Client A"):
        return self.post("/clients", {"name": name})["id"]

    def book(self, client, required, hours, day):
        return self.post("/jobs/book", {"client_id": client, "cleaners_required": required, "hours": hours, "requested_day": day})

    def tap(self, kind, cleaner, job, when):
        return self.post(f"/field/{cleaner}/jobs/{job}/{kind}", {"at": when})

    def state(self, invoices=False):
        return [self.get(p) for p in ["/cleaners", "/clients", "/jobs"] + (["/invoices"] if invoices else [])]


def cleaners_of(job):
    """the job's cleaners, by id (the plan leaves the order of assignments open)"""
    return sorted(a["cleaner_id"] for a in job["assignments"])


def slot(job):
    """(day, minute) of the job's start"""
    d, t = job["booked_start"].split("T")
    h, m = t.split(":")[:2]
    return d, int(h) * 60 + int(m)


def assert_no_overlaps(jobs):
    """Scheduled jobs: weekdays, 8:00 to 17:00, an hour apart per cleaner (data-model invariants 1, 2)."""
    per = {}
    for j in jobs:
        if j["state"] != "scheduled":
            continue
        d, s = slot(j)
        e = s + j["expected_length_min"]
        assert date.fromisoformat(d).weekday() < 5 and s >= 480 and e <= 1020, j
        for c in cleaners_of(j):
            per.setdefault((c, d), []).append((s, e))
    for k, xs in per.items():
        xs.sort()
        for (s1, e1), (s2, e2) in zip(xs, xs[1:]):
            assert s2 >= e1 + 60, f"cleaner {k[0]} on {k[1]}: {s1}-{e1} then {s2}-{e2}"


@pytest.fixture
def app(tmp_path):
    a = App(tmp_path / "store.json")
    yield a
    a.stop()
