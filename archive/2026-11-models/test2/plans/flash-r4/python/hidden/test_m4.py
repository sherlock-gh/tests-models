from conftest import MON, spacing

def test_removals_and_unknown_ids(probe):
    a = probe.cleaner()
    c = probe.client()
    j1 = probe.book(c, 1, 1)
    j2 = probe.book(c, 1, 1)
    b = probe.cleaner('Bo')
    deleted = probe.ok('DELETE', f'/api/cleaners/{a}')
    assert set(deleted['rebooked_job_ids']) == {j1['id'], j2['id']}
    for jid in deleted['rebooked_job_ids']:
        j = probe.ok('GET', f'/api/jobs/{jid}')['job']
        assert j['parts'][0]['assignments'][0]['cleaner_id'] == b
    spacing(probe.ok('GET', '/api/jobs')['jobs'])
    cancelled = probe.ok('DELETE', f'/api/clients/{c}')
    assert set(cancelled['cancelled_job_ids']) == {j1['id'], j2['id']}
    assert all(probe.ok('GET', f'/api/jobs/{jid}')['job']['status'] == 'cancelled'
               for jid in cancelled['cancelled_job_ids'])
    probe.reject('DELETE', '/api/jobs/9999', code=404)
    probe.reject('PUT', '/api/cleaners/9999', {'name': 'X', 'phone': '555', 'email': 'x@y'}, 404)

def test_job_edit_keeps_slot_or_refuses_conflict(probe):
    probe.cleaner()
    c = probe.client()
    first = probe.book(c, 1, 1)
    second = probe.book(c, 1, 1)
    base = {'client_id': c, 'cleaners_needed': 1, 'requested_day': MON}
    probe.reject('PUT', f"/api/jobs/{first['id']}", {**base, 'expected_length_hours': 2}, 409)
    changed = probe.ok('PUT', f"/api/jobs/{first['id']}", {**base, 'expected_length_hours': .5})['job']
    assert changed['parts'][0]['start'] == first['parts'][0]['start']
    assert changed['parts'][0]['end'] == MON + 'T08:30'
    spacing(probe.ok('GET', '/api/jobs')['jobs'])

def test_issued_job_cannot_be_deleted(probe):
    a = probe.cleaner()
    c = probe.client()
    job = probe.book(c, 1, 1)
    probe.tap(job['id'], a, 'arrive', MON + 'T08:00')
    probe.tap(job['id'], a, 'depart', MON + 'T09:00')
    probe.reject('DELETE', f"/api/jobs/{job['id']}", code=409)
