"""Drive the contracted desktop API in-process against an isolated data file."""
import os
import sys
from pathlib import Path
import pytest

TARGET = Path(os.environ['TARGET'])
sys.path.insert(0, str(TARGET / 'desktop'))
MON, TUE, WED, FRI, SAT, NEXT = ('2027-11-15', '2027-11-16', '2027-11-17',
                                  '2027-11-19', '2027-11-20', '2027-11-22')

class Probe:
    def __init__(self, path):
        from app import create_app
        self.path = path
        self.app = create_app(path)

    def call(self, method, url, body=None):
        # The contract writes a record reply as {cleaner}, {client}, {job}, {invoice}: the record
        # itself or wrapped under its name both read it (owner, 17 Nov), so a bare one is wrapped here.
        status, value = self.app.request(method, url, body)
        if isinstance(value, dict) and 'id' in value and 'error' not in value:
            value = {**{k: value for k in ('cleaner', 'client', 'job', 'invoice')}, **value}
        return status, value

    def ok(self, method, url, body=None, code=200):
        status, value = self.call(method, url, body)
        assert status == code, (method, url, body, status, value)
        return value

    def reject(self, method, url, body=None, code=None):
        before = self.path.read_bytes() if self.path.exists() else None
        status, result = self.call(method, url, body)
        assert status in (400, 404, 409) and (code is None or status == code), (status, result)
        assert isinstance(result.get('error'), str) and result['error']
        assert before == (self.path.read_bytes() if self.path.exists() else None)
        assert self.ok('GET', '/api/cleaners')['cleaners'] is not None
        return result['error']

    def cleaner(self, name='Ann'):
        return self.ok('POST', '/api/cleaners', {'name': name, 'phone': '555', 'email': 'a@example.test'}, 201)['cleaner']['id']

    def client(self):
        return self.ok('POST', '/api/clients', {'name': 'Pat', 'address': '1 Main', 'phone': '555'}, 201)['client']['id']

    def book(self, client, n, hours, day=MON):
        return self.ok('POST', '/api/jobs', {'client_id': client, 'cleaners_needed': n,
                       'expected_length_hours': hours, 'requested_day': day}, 201)['job']

    def tap(self, job, cleaner, kind, when):
        return self.ok('POST', '/api/assignments/tap', {'job_id': job, 'cleaner_id': cleaner,
                       'kind': kind, 'at': when})['job']

@pytest.fixture
def probe(tmp_path):
    return Probe(tmp_path / 'data.json')

def assigned(part):
    return [a['cleaner_id'] for a in part['assignments']]

def spacing(jobs):
    from datetime import datetime, timedelta
    per = {}
    for job in jobs:
        if job['status'] == 'cancelled':
            continue
        for p in job['parts']:
            s = datetime.fromisoformat(p['start'])
            assert s.weekday() < 5 and s.hour >= 8 and s.minute % 15 == 0
            for a in p['assignments']:
                end = datetime.fromisoformat(p['end']) + timedelta(minutes=a['extended_minutes'])
                per.setdefault(a['cleaner_id'], []).append((s, end))
    for entries in per.values():
        for left, right in zip(sorted(entries), sorted(entries)[1:]):
            assert right[0] >= left[1] + timedelta(hours=1), entries
