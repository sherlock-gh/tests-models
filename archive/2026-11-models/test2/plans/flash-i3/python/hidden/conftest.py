"""Hidden tests for the desktop app (Flash-Next's iteration 3 plan): each test starts the build's
app (`python -m desktop.server` in TARGET, the repo, with its .venv's Python if it has one) on a
fresh CLEANING_DATA file and a free PORT, and drives its JSON API (contracts/desktop-api.md and
exact-interfaces.md). Monday 2027-11-15 is the first test day; no clock change falls in the weeks used."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

TARGET = Path(os.environ["TARGET"])
MON, TUE, WED, THU, FRI, SAT = "2027-11-15", "2027-11-16", "2027-11-17", "2027-11-18", "2027-11-19", "2027-11-20"
NEXT_MON = "2027-11-22"
NO_SLOT = "No slot for this job within 90 days of the requested day."


def T(day, hm):
    return f"{day}T{hm}"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App:
    def __init__(self, data):
        self.data = data
        self.start()

    def start(self):
        self.port = free_port()
        py = TARGET / ".venv" / "bin" / "python"
        self.log = open(self.data.with_suffix(".log"), "ab")
        env = {**os.environ, "PORT": str(self.port), "CLEANING_DATA": str(self.data), "TZ": "America/Los_Angeles"}
        env.pop("PYTHONPATH", None)
        self.proc = subprocess.Popen([str(py) if py.exists() else sys.executable, "-m", "desktop.server"], cwd=TARGET,
                                     env=env, stdout=self.log, stderr=self.log)
        for _ in range(150):
            if self.proc.poll() is not None:
                pytest.fail(f"the app exited at start: {self.data.with_suffix('.log').read_text()[-800:]}")
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

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw.decode(errors="replace")

    def ok(self, method, path, body=None, status=(200,)):
        st, out = self.call(method, path, body)
        assert st in status and not (isinstance(out, dict) and "error" in out), f"{method} {path} {body}: {st} {out}"
        return out

    def get(self, path):
        return self.ok("GET", path)

    def post(self, path, body=None):
        return self.ok("POST", path, body or {}, status=(200, 201))

    def put(self, path, body):
        return self.ok("PUT", path, body)

    def delete(self, path):
        return self.ok("DELETE", path)

    def fails(self, method, path, body=None, status=(400, 404)):
        """An error answer ({"error": message} with 400, or 404 for an unknown record) that leaves
        the data file as it was and the app answering."""
        before = self.data.read_bytes() if self.data.exists() else None
        if body is None and method in ("POST", "PUT"):
            body = {}
        st, out = self.call(method, path, body)
        assert st in status and isinstance(out, dict) and isinstance(out.get("error"), str) and out["error"], \
            f"{method} {path} {body}: expected an error ({status}), got {st} {out}"
        after = self.data.read_bytes() if self.data.exists() else None
        assert after == before, f"{method} {path} {body}: the data file changed on an error"
        assert self.call("GET", "/api/cleaners")[0] == 200, "the app stopped answering after an error"
        return out

    # helpers
    def cleaners(self, n, first=0):
        return [self.post("/api/cleaners", {"name": f"Cleaner {first + i}"})["id"] for i in range(n)]

    def client(self, name="Client A"):
        return self.post("/api/clients", {"name": name})["id"]

    def book(self, client, needed, minutes, day):
        return self.post("/api/jobs", {"client_id": client, "cleaners_needed": needed, "expected_length_min": minutes, "requested_day": day})

    def job(self, jid):
        return self.get(f"/api/jobs/{jid}")

    def jobs(self):
        return self.get("/api/jobs")["jobs"]

    def tap(self, kind, job, cleaner, when):
        return self.post(f"/api/jobs/{job}/{kind}", {"cleaner_id": cleaner, "at": when})

    def invoices(self):
        return self.get("/api/invoices")["invoices"]


def spans(job):
    return [(p["start"], p["end"]) for p in job["parts"]]


def start(job):
    return job["parts"][0]["start"]


def assert_no_overlaps(jobs):
    """Booked parts: weekdays, on the quarter hour from 8:00, ending by 17:00; for each cleaner,
    every part starts at least an hour after the other's end (rules-core I1-I3)."""
    per = {}
    for j in jobs:
        if j["status"] == "cancelled":
            continue
        for p in j["parts"]:
            s, e = datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"])
            if j["status"] == "booked":
                assert s.weekday() < 5 and s.minute % 15 == 0 and s.hour >= 8 and e <= s.replace(hour=17, minute=0), j
            for c in j["cleaner_ids"]:
                per.setdefault(c, []).append((s, e, j["id"]))
    for c, xs in per.items():
        xs.sort()
        for (s1, e1, j1), (s2, e2, j2) in zip(xs, xs[1:]):
            assert s2 >= e1 + timedelta(hours=1), f"cleaner {c}: job {j1} {s1}-{e1}, then job {j2} {s2}-{e2}"


@pytest.fixture
def app(tmp_path):
    a = App(tmp_path / "data.json")
    yield a
    a.stop()
