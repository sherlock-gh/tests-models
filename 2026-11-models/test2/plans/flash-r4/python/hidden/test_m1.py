from conftest import MON, TUE, FRI, SAT, NEXT, assigned, spacing

def test_booking_grid_spacing_and_refusals(probe):
    a = probe.cleaner()
    c = probe.client()
    first = probe.book(c, 1, 4)
    assert first['parts'][0]['start'] == MON + 'T08:00'
    assert first['parts'][0]['end'] == MON + 'T12:00'
    second = probe.book(c, 1, 1)
    assert second['parts'][0]['start'] == MON + 'T13:00'
    spacing([first, second])
    for n, h in [(0, 1), (4, 1), (1, 0), (1, -2)]:
        probe.reject('POST', '/api/jobs', {'client_id': c, 'cleaners_needed': n,
                     'expected_length_hours': h, 'requested_day': MON}, 400)
    probe.reject('POST', '/api/jobs', {'client_id': 900, 'cleaners_needed': 1,
                 'expected_length_hours': 1, 'requested_day': MON}, 404)
    assert probe.ok('GET', '/api/cleaners/' + str(a))['cleaner']['name'] == 'Ann'

def test_minutes_weekends_and_split_replacement(probe):
    a = probe.cleaner()
    c = probe.client()
    first = probe.book(c, 1, 250 / 60)
    assert first['parts'][0]['end'] == MON + 'T12:10'
    assert probe.book(c, 1, .5)['parts'][0]['start'] == MON + 'T13:15'
    b = probe.cleaner('Bo')
    assert probe.book(c, 1, 2, SAT)['parts'][0]['start'] == NEXT + 'T08:00'
    job = probe.book(c, 1, 10, FRI)
    assert [p['day'] for p in job['parts']] == [FRI, NEXT]
    assert [p['end'][11:] for p in job['parts']] == ['16:00', '10:00']
    assert all(len(assigned(p)) == 1 for p in job['parts'])
    spacing(probe.ok('GET', '/api/jobs')['jobs'])

def test_later_part_can_choose_another_free_cleaner(probe):
    a, b = probe.cleaner(), probe.cleaner('Bo')
    c = probe.client()
    occupied = probe.book(c, 1, 8, MON)
    assert assigned(occupied['parts'][0]) == [a]
    split = probe.book(c, 1, 10, MON)
    assert assigned(split['parts'][0]) == [b]
    assert split['parts'][1]['day'] == TUE
    assert len(assigned(split['parts'][1])) == 1
    spacing(probe.ok('GET', '/api/jobs')['jobs'])

def test_later_part_prefers_original_crew_but_replaces_unavailable_member(probe):
    a, b = probe.cleaner(), probe.cleaner('Bo')
    c = probe.client()
    occupied = probe.book(c, 1, 8, TUE)
    assert assigned(occupied['parts'][0]) == [a]
    split = probe.book(c, 1, 10, MON)
    assert assigned(split['parts'][0]) == [a]
    assert split['parts'][1]['day'] == TUE
    assert assigned(split['parts'][1]) == [b]
    spacing(probe.ok('GET', '/api/jobs')['jobs'])

def test_sixty_minutes_is_strict_at_the_boundary(probe):
    probe.cleaner()
    c = probe.client()
    first = probe.book(c, 1, 241 / 60)
    assert first['parts'][0]['end'] == MON + 'T12:01'
    assert probe.book(c, 1, .5)['parts'][0]['start'] == MON + 'T13:15'

def test_horizon_is_atomic(probe):
    probe.cleaner()
    c = probe.client()
    for _ in range(65):
        probe.book(c, 1, 8)
    message = probe.reject('POST', '/api/jobs', {'client_id': c, 'cleaners_needed': 1,
                            'expected_length_hours': 8, 'requested_day': MON}, 409)
    assert '90' in message
