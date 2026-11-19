from conftest import MON, spacing

def test_extension_rebooks_at_hour_floor(probe):
    a = probe.cleaner()
    c = probe.client()
    first = probe.book(c, 1, 4)
    later = probe.book(c, 1, 1)
    assert later['parts'][0]['start'] == MON + 'T13:00'
    probe.tap(first['id'], a, 'arrive', MON + 'T08:00')
    for _ in range(3):
        response = probe.ok('POST', '/api/assignments/extend', {'job_id': first['id'],
                            'cleaner_id': a, 'minutes': 20, 'at': MON + 'T11:00'})
    assert response['job']['parts'][0]['assignments'][0]['extended_minutes'] == 60
    assert probe.ok('GET', f"/api/jobs/{later['id']}")['job']['parts'][0]['start'] >= MON + 'T14:00'
    spacing(probe.ok('GET', '/api/jobs')['jobs'])
    probe.tap(first['id'], a, 'depart', MON + 'T12:00')
    probe.reject('POST', '/api/assignments/extend', {'job_id': first['id'],
                 'cleaner_id': a, 'minutes': 20, 'at': MON + 'T12:01'}, 409)

def test_coworkers_later_job_moves_with_extension(probe):
    a, b = probe.cleaner(), probe.cleaner('Bo')
    c = probe.client()
    first = probe.book(c, 2, 4)
    later = probe.book(c, 1, 1)
    assert later['parts'][0]['assignments'][0]['cleaner_id'] == a
    probe.tap(first['id'], b, 'arrive', MON + 'T08:00')
    for _ in range(3):
        result = probe.ok('POST', '/api/assignments/extend', {'job_id': first['id'],
                          'cleaner_id': b, 'minutes': 20, 'at': MON + 'T11:00'})
    assert probe.ok('GET', f"/api/jobs/{later['id']}")['job']['parts'][0]['start'] >= MON + 'T14:00'
    spacing(probe.ok('GET', '/api/jobs')['jobs'])

def test_extension_can_pass_workday(probe):
    a = probe.cleaner()
    c = probe.client()
    job = probe.book(c, 1, 8)
    probe.tap(job['id'], a, 'arrive', MON + 'T08:00')
    for _ in range(4):
        response = probe.ok('POST', '/api/assignments/extend', {'job_id': job['id'],
                            'cleaner_id': a, 'minutes': 20, 'at': MON + 'T12:00'})
    assert response['job']['parts'][0]['assignments'][0]['extended_minutes'] == 80
