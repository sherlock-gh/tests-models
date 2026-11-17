"""Single-file atomic store with serialized transactions."""
import copy
import json
import os
import tempfile
import threading
from pathlib import Path

LOCK = threading.RLock()


def empty():
    return {'cleaners': [], 'clients': [], 'jobs': [], 'invoices': [],
            'counters': {'cleaners': 0, 'clients': 0, 'jobs': 0, 'invoices': 0}}


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        with LOCK:
            try:
                value = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(value, dict) or any(k not in value for k in empty()):
                    return empty()
                return value
            except (OSError, ValueError, TypeError):
                return empty()

    def change(self, action):
        with LOCK:
            state = copy.deepcopy(self.read())
            result = action(state)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.data-')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(state, stream, ensure_ascii=False, separators=(',', ':'))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return copy.deepcopy(result)


def issue(state, type_name):
    state['counters'][type_name] += 1
    return state['counters'][type_name]


def get(state, type_name, identifier):
    from .errors import missing
    record = next((item for item in state[type_name] if item['id'] == identifier), None)
    if record is None:
        missing(f'{type_name[:-1]} {identifier} does not exist')
    return record
