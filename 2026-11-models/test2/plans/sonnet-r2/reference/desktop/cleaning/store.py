"""The local JSON file (research D2): missing file is empty data; every save is atomic (temp file, then rename)."""
import json
import os
import tempfile

EMPTY = {"nextIds": {"cleaner": 0, "client": 0, "job": 0, "invoice": 0},
         "cleaners": [], "clients": [], "jobs": [], "invoices": [], "payments": []}


class Store:
    def __init__(self, path):
        self.path = path

    def load(self):
        if not os.path.exists(self.path):
            return json.loads(json.dumps(EMPTY))
        with open(self.path) as f:
            return json.load(f)

    def save(self, state):
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".data-")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.path)
