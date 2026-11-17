"""In-process end-to-end contract smoke, runnable with unittest discovery."""
import io
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from app import create_app


class DesktopFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'data.json'
        self.app = create_app(self.path)

    def call(self, method, path, body=None, expect=200):
        raw = json.dumps(body).encode() if body is not None else b''
        status = []
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path.split('?')[0],
               'QUERY_STRING': path.partition('?')[2], 'CONTENT_LENGTH': str(len(raw)),
               'wsgi.input': io.BytesIO(raw)}
        output = b''.join(self.app(env, lambda code, headers: status.append(code)))
        self.assertEqual(int(status[0][:3]), expect, output)
        return json.loads(output)

    def base(self, n=3):
        cleaners = [self.call('POST', '/api/cleaners', {'name': f'C{i}', 'phone': '123', 'email': 'c@x'}, 201)['cleaner']['id'] for i in range(n)]
        client = self.call('POST', '/api/clients', {'name': 'A', 'address': 'Street', 'phone': '123'}, 201)['client']['id']
        return cleaners, client

    def book(self, client, hours, on='2026-11-16', count=1):
        return self.call('POST', '/api/jobs', {'client_id': client, 'cleaners_needed': count,
                         'expected_length_hours': hours, 'requested_day': on}, 201)['job']

    def test_booking_split_and_persistence(self):
        cleaners, cid = self.base(1)
        first = self.book(cid, 4)
        second = self.book(cid, 2)
        self.assertEqual(second['parts'][0]['start'], '2026-11-16T13:00')
        split = self.book(cid, 10, '2026-11-21')
        self.assertEqual([p['day'] for p in split['parts']], ['2026-11-23', '2026-11-24'])
        self.assertEqual([p['end'][-5:] for p in split['parts']], ['16:00', '10:00'])
        self.assertEqual([p['assignments'][0]['cleaner_id'] for p in split['parts']], [1, 1])
        before = self.path.read_bytes()
        self.call('POST', '/api/jobs', {'client_id': cid, 'cleaners_needed': 3,
                  'expected_length_hours': -1, 'requested_day': '2026-11-16'}, 400)
        self.assertEqual(self.path.read_bytes(), before)
        fresh = create_app(self.path)
        self.assertEqual(fresh.request('GET', '/api/jobs')[1]['jobs'][-1], split)
        self.call('DELETE', '/api/jobs/' + str(first['id']))
        new = self.book(cid, 1)
        self.assertGreater(new['id'], split['id'])

    def test_taps_invoice_payment_utilization(self):
        cleaners, cid = self.base(2)
        job = self.book(cid, 4, count=2)
        for cleaner, arrive, depart in [(1, '08:00', '11:30'), (2, '08:00', '12:00')]:
            data = {'job_id': job['id'], 'cleaner_id': cleaner, 'kind': 'arrive', 'at': '2026-11-16T'+arrive}
            self.call('POST', '/api/assignments/tap', data)
            before = self.path.read_bytes()
            self.call('POST', '/api/assignments/tap', data, 409)
            self.assertEqual(self.path.read_bytes(), before)
            data.update(kind='depart', at='2026-11-16T'+depart)
            job = self.call('POST', '/api/assignments/tap', data)['job']
        invoice = self.call('GET', f'/api/invoices/{job["invoice_id"]}')['invoice']
        self.assertEqual([x['amount_cents'] for x in invoice['lines']], [15750, 18000])
        self.assertEqual(invoice['total_cents'], 33750)
        before = self.path.read_bytes()
        self.call('POST', f'/api/invoices/{invoice["id"]}/payment', {'amount_cents': 33700}, 409)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.call('POST', f'/api/invoices/{invoice["id"]}/payment', {'amount_cents': 33750})['invoice']['settled'])
        self.call('DELETE', f'/api/jobs/{job["id"]}', expect=409)
        daily = self.call('GET', '/api/utilization?cleaner_id=1&from=2026-11-16&to=2026-11-17')
        self.assertEqual(daily['days'][0]['minutes'], 210)
        self.assertEqual(daily['weeks'][0]['of'], 2400)

    def test_extension_cascade_and_removals(self):
        cleaners, cid = self.base(3)
        first = self.book(cid, 4, count=2)
        following = self.book(cid, 2, count=2)
        self.call('POST', '/api/assignments/tap', {'job_id': first['id'], 'cleaner_id': 1,
                  'kind': 'arrive', 'at': '2026-11-16T08:00'})
        for step in range(3):
            response = self.call('POST', '/api/assignments/extend', {'job_id': first['id'], 'cleaner_id': 1,
                              'minutes': 20, 'at': '2026-11-16T11:00'})
        self.assertIn(following['id'], response['rebooked_job_ids'] if step == 2 else [following['id']])
        moved = self.call('GET', f'/api/jobs/{following["id"]}')['job']
        self.assertGreaterEqual(moved['parts'][0]['start'], '2026-11-16T14:00')
        self.assertEqual(self.call('DELETE', '/api/cleaners/2')['rebooked_job_ids'], [following['id']])
        self.assertEqual(self.call('GET', f'/api/jobs/{following["id"]}')['job']['parts'][0]['assignments'][0]['cleaner_id'], 1)
        cancelled = self.call('DELETE', f'/api/clients/{cid}')['cancelled_job_ids']
        self.assertIn(following['id'], cancelled)
        self.assertNotIn(first['id'], cancelled)
        self.assertEqual(self.call('GET', f'/api/jobs/{first["id"]}')['job']['status'], 'booked')

    def test_overnight_and_uncapped(self):
        _, cid = self.base(1)
        job = self.book(cid, 1)
        self.call('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': 1,
                  'kind': 'arrive', 'at': '2026-11-16T22:00'})
        self.call('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': 1,
                  'kind': 'depart', 'at': '2026-11-17T02:00'})
        day = self.call('GET', '/api/utilization?cleaner_id=1&from=2026-11-16&to=2026-11-17')['days']
        self.assertEqual([entry['minutes'] for entry in day], [120, 120])
        job = self.book(cid, 1, '2026-11-18')
        self.call('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': 1,
                  'kind': 'arrive', 'at': '2026-11-18T08:00'})
        self.call('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': 1,
                  'kind': 'depart', 'at': '2026-11-18T17:00'})
        minutes = self.call('GET', '/api/utilization?cleaner_id=1&from=2026-11-18&to=2026-11-18')['days'][0]['minutes']
        self.assertEqual(minutes, 540)

    def test_independent_split_cleaners_and_refusal(self):
        _, cid = self.base(2)
        blocking = self.book(cid, 8, '2026-11-17')
        self.assertEqual(blocking['parts'][0]['assignments'][0]['cleaner_id'], 1)
        split = self.book(cid, 10, '2026-11-16')
        self.assertEqual(split['parts'][0]['assignments'][0]['cleaner_id'], 1)
        self.assertEqual(split['parts'][1]['assignments'][0]['cleaner_id'], 2)
        self.assertEqual(split['parts'][1]['day'], '2026-11-17')
        before = self.path.read_bytes()
        self.call('POST', '/api/jobs', {'client_id': cid, 'cleaners_needed': 3,
                  'expected_length_hours': 1, 'requested_day': '2026-11-16'}, 409)
        self.assertEqual(self.path.read_bytes(), before)

    def test_unplaceable_cascade_is_atomic(self):
        _, cid = self.base(1)
        anchor = date.fromisoformat('2026-11-16')
        first = self.book(cid, 4)
        following = self.book(cid, 4)
        for offset in range(1, 91):
            on = anchor + timedelta(days=offset)
            if on.weekday() < 5:
                self.book(cid, 8, on.isoformat())
        self.call('POST', '/api/assignments/tap', {'job_id': first['id'], 'cleaner_id': 1,
                  'kind': 'arrive', 'at': '2026-11-16T08:00'})
        before = self.path.read_bytes()
        self.call('POST', '/api/assignments/extend', {'job_id': first['id'], 'cleaner_id': 1,
                  'minutes': 20, 'at': '2026-11-16T11:00'}, 409)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.call('GET', f'/api/jobs/{following["id"]}')['job']['parts'][0]['start'], '2026-11-16T13:00')

    def test_off_quarter_end_and_spacing(self):
        _, cid = self.base(1)
        first = self.book(cid, 4 + 10 / 60)
        self.assertEqual(first['parts'][0]['end'], '2026-11-16T12:10')
        following = self.book(cid, 1)
        self.assertEqual(following['parts'][0]['start'], '2026-11-16T13:15')

    def test_crud_and_day_views(self):
        _, cid = self.base(2)
        job = self.book(cid, 2)
        self.assertEqual(len(self.call('GET', '/api/day?cleaner_id=1&on=2026-11-16')['parts']), 1)
        edited = self.call('PUT', f'/api/jobs/{job["id"]}', {'client_id': cid,
               'cleaners_needed': 1, 'expected_length_hours': 3, 'requested_day': '2026-11-16'})['job']
        self.assertEqual(edited['parts'][0]['end'], '2026-11-16T11:00')
        split = self.call('PUT', f'/api/jobs/{job["id"]}', {'client_id': cid,
                  'cleaners_needed': 1, 'expected_length_hours': 10, 'requested_day': '2026-11-16'})['job']
        self.assertEqual([p['part_index'] for p in split['parts']], [0, 1])
        self.assertEqual(split['parts'][1]['day'], '2026-11-17')
        self.call('PUT', '/api/cleaners/1', {'name': 'New name', 'phone': '555', 'email': 'new@x'})
        self.assertEqual(self.call('GET', '/api/cleaners/1')['cleaner']['name'], 'New name')
        self.call('PUT', '/api/clients/1', {'name': 'New client', 'address': 'Here', 'phone': '555'})
        self.assertEqual(self.call('GET', '/api/clients/1')['client']['name'], 'New client')
        self.assertEqual([j['id'] for j in self.call('GET', '/api/jobs?from=2026-11-17')['jobs']], [job['id']])


if __name__ == '__main__':
    unittest.main()
