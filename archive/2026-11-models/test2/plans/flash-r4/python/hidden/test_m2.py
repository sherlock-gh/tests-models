from conftest import MON, assigned

def test_taps_invoice_exact_payment(probe):
    a, b = probe.cleaner('Ann'), probe.cleaner('Bo')
    c = probe.client()
    job = probe.book(c, 2, 4)
    assert set(assigned(job['parts'][0])) == {a, b}
    assert probe.ok('GET', f'/api/day?cleaner_id={a}&on={MON}')['parts']
    probe.reject('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': a,
                 'kind': 'depart', 'at': MON + 'T11:30'}, 409)
    probe.tap(job['id'], a, 'arrive', MON + 'T08:00')
    probe.reject('POST', '/api/assignments/tap', {'job_id': job['id'], 'cleaner_id': a,
                 'kind': 'arrive', 'at': MON + 'T09:00'}, 409)
    probe.tap(job['id'], a, 'depart', MON + 'T11:30')
    assert probe.ok('GET', '/api/invoices')['invoices'] == []
    probe.tap(job['id'], b, 'arrive', MON + 'T08:00')
    result = probe.tap(job['id'], b, 'depart', MON + 'T12:00')
    assert result['invoice_id'] is not None
    iid = result['invoice_id']
    invoice = probe.ok('GET', f'/api/invoices/{iid}')['invoice']
    assert {(line['cleaner_id'], line['minutes_worked'], line['amount_cents'])
            for line in invoice['lines']} == {(a, 210, 15750), (b, 240, 18000)}
    assert invoice['total_cents'] == 33750 and not invoice['settled']
    probe.reject('POST', f'/api/invoices/{iid}/payment', {'amount_cents': 33700}, 409)
    assert len(probe.ok('GET', '/api/invoices?settled=false')['invoices']) == 1
    paid = probe.ok('POST', f'/api/invoices/{iid}/payment', {'amount_cents': 33750})['invoice']
    assert paid['settled'] and paid['payment']['amount_cents'] == 33750
    assert len(probe.ok('GET', '/api/invoices?settled=true')['invoices']) == 1

def test_every_split_assignment_must_depart(probe):
    a, b = probe.cleaner(), probe.cleaner('Bo')
    c = probe.client()
    job = probe.book(c, 2, 10)
    for p in job['parts']:
        for item in p['assignments']:
            cid = item['cleaner_id']
            probe.tap(job['id'], cid, 'arrive', p['start'])
            result = probe.tap(job['id'], cid, 'depart', p['end'])
            if p['part_index'] == 0:
                assert result['invoice_id'] is None
    assert result['invoice_id'] is not None
