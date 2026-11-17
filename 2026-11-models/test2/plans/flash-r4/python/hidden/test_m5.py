from conftest import MON, TUE

def test_utilization_and_restart(probe):
    a = probe.cleaner()
    c = probe.client()
    j = probe.book(c, 1, 8)
    probe.tap(j['id'], a, 'arrive', MON + 'T08:00')
    probe.tap(j['id'], a, 'depart', MON + 'T17:00')
    report = probe.ok('GET', f'/api/utilization?cleaner_id={a}&from={MON}&to={TUE}')
    monday = next(d for d in report['days'] if d['date'] == MON)
    assert monday['minutes'] == 540 and monday['of'] == 480
    assert report['weeks'][0]['minutes'] == 540 and report['weeks'][0]['of'] == 2400
    from conftest import Probe
    reopened = Probe(probe.path)
    assert reopened.ok('GET', f"/api/jobs/{j['id']}")['job']['invoice_id'] is not None
    assert reopened.ok('GET', '/api/invoices')['invoices'][0]['total_cents'] == 40500

def test_errors_are_atomic_and_app_recovers(probe):
    a = probe.cleaner()
    c = probe.client()
    probe.reject('POST', '/api/jobs', {'client_id': c, 'cleaners_needed': 1,
                 'expected_length_hours': 1, 'requested_day': 'invalid'}, 400)
    probe.reject('GET', '/api/day?cleaner_id=9999&on=2027-11-15', code=404)
    assert probe.book(c, 1, 1)['parts'][0]['assignments'][0]['cleaner_id'] == a
