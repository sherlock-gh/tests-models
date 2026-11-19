"""First-fit booking, split parts, safe edits and rebooking."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from .errors import bad, conflict
from .store import get, issue
from .timezone_util import ZONE, day, clock, grid, instant, text


def future(job):
    return all(a['arrive'] is None for p in job['parts'] for a in p['assignments'])


def lengths(hours):
    try:
        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise ValueError()
        total = Decimal(str(hours)) * 60
        if not total.is_finite() or total <= 0:
            raise ValueError()
        nearest = total.to_integral_value(rounding=ROUND_HALF_UP)
        total = max(1, int(nearest if abs(total - nearest) < Decimal('0.000001')
                           else total.to_integral_value(rounding=ROUND_CEILING)))
    except (InvalidOperation, ValueError, OverflowError):
        bad('expected_length_hours must be positive in whole minutes')
    result = []
    while total:
        length = min(total, 480)
        result.append(length)
        total -= length
    return result


def validate(state, fields):
    required = ('client_id', 'cleaners_needed', 'expected_length_hours', 'requested_day')
    if not isinstance(fields, dict) or any(key not in fields for key in required):
        bad('job requires client_id, cleaners_needed, expected_length_hours and requested_day')
    client = fields['client_id']
    needed = fields['cleaners_needed']
    if isinstance(client, bool) or not isinstance(client, int):
        bad('client_id must be an integer')
    get(state, 'clients', client)
    if isinstance(needed, bool) or not isinstance(needed, int) or needed not in (1, 2, 3):
        bad('cleaners_needed must be 1, 2 or 3')
    pieces = lengths(fields['expected_length_hours'])
    requested = day(fields['requested_day'])
    return pieces, requested


def busy(state, cleaner_id, start, end, skip_job=None):
    for job in state['jobs']:
        if job['status'] != 'booked' or job['id'] == skip_job:
            continue
        for part in job['parts']:
            for assignment in part['assignments']:
                if assignment['cleaner_id'] != cleaner_id:
                    continue
                other_start = instant(part['start'])
                other_end = instant(part['end']) + timedelta(minutes=assignment['extended_minutes'])
                if start < other_start:
                    if other_start < end + timedelta(hours=1):
                        return True
                elif start < other_end + timedelta(hours=1):
                    return True
    return False


def free_at(state, start, end, preferred=(), skip_job=None):
    available = [c['id'] for c in sorted(state['cleaners'], key=lambda c: c['id'])
                 if not busy(state, c['id'], start, end, skip_job)]
    return [cid for cid in preferred if cid in available] + [cid for cid in available if cid not in preferred]


def place(state, requested, durations, needed, floor=None, start_day=None, preferred=()):
    """Place all parts, respecting original horizon even if cascade floor moves."""
    last_day = requested + timedelta(days=90)
    earliest_day = start_day or requested
    parts = []
    for index, duration in enumerate(durations):
        found = None
        current = earliest_day
        while current <= last_day and found is None:
            if current.weekday() < 5:
                for candidate in grid(current):
                    end = candidate + timedelta(minutes=duration)
                    if end.hour > 17 or (end.hour == 17 and end.minute > 0):
                        continue
                    if floor is not None and instant(candidate) < instant(floor):
                        continue
                    ids = free_at(state, instant(candidate), instant(end), preferred)
                    if len(ids) >= needed:
                        found = {'part_index': index, 'day': current.isoformat(),
                                 'start': text(candidate), 'end': text(end),
                                 'assignments': [{'cleaner_id': cid, 'arrive': None,
                                                  'depart': None, 'extended_minutes': 0}
                                                 for cid in ids[:needed]]}
                        break
            current += timedelta(days=1)
        if found is None:
            conflict('No slot in 90 days for the requested job')
        parts.append(found)
        if index == 0 and not preferred:
            preferred = tuple(a['cleaner_id'] for a in found['assignments'])
        earliest_day = day(found['day']) + timedelta(days=1)
        floor = None
    return parts


def book(state, fields):
    durations, requested = validate(state, fields)
    parts = place(state, requested, durations, fields['cleaners_needed'])
    job = {'id': issue(state, 'jobs'), 'client_id': fields['client_id'],
           'cleaners_needed': fields['cleaners_needed'],
           'expected_length_hours': fields['expected_length_hours'],
           'requested_day': fields['requested_day'], 'status': 'booked',
           'parts': parts, 'invoice_id': None}
    state['jobs'].append(job)
    return job


def rebook(state, job, floor=None):
    if not future(job):
        conflict('cannot rebook a job already arrived at')
    state['jobs'].remove(job)
    job['parts'] = place(state, day(job['requested_day']),
                         lengths(job['expected_length_hours']), job['cleaners_needed'], floor)
    state['jobs'].append(job)
    return job


def delete_cleaner(state, cid):
    get(state, 'cleaners', cid)
    affected = sorted((j for j in state['jobs'] if j['status'] == 'booked' and future(j)
                       and any(a['cleaner_id'] == cid for p in j['parts'] for a in p['assignments'])),
                      key=lambda j: (j['parts'][0]['start'], j['id']))
    state['cleaners'] = [c for c in state['cleaners'] if c['id'] != cid]
    # Remove all affected jobs first so a formerly later booking does not block an earlier one.
    state['jobs'] = [j for j in state['jobs'] if j not in affected]
    for job in affected:
        job['parts'] = place(state, day(job['requested_day']),
                             lengths(job['expected_length_hours']), job['cleaners_needed'])
        state['jobs'].append(job)
    return {'ok': True, 'rebooked_job_ids': [j['id'] for j in affected]}


def delete_client(state, cid):
    get(state, 'clients', cid)
    affected = [j for j in state['jobs'] if j['client_id'] == cid and j['status'] == 'booked' and future(j)]
    for job in affected:
        job['status'] = 'cancelled'
    state['clients'] = [c for c in state['clients'] if c['id'] != cid]
    return {'ok': True, 'cancelled_job_ids': [j['id'] for j in affected]}


def edit(state, job, fields):
    durations, requested = validate(state, fields)
    if job['invoice_id'] is not None or not future(job):
        conflict('cannot edit a job already arrived at or invoiced')
    if job['status'] != 'booked':
        conflict('cannot edit cancelled job')
    parts = job['parts']
    if requested > day(parts[0]['day']):
        conflict('requested day is later than booked start; new booking required')
    for part, duration in zip(parts[:len(durations)], durations):
        end = clock(part['start']) + timedelta(minutes=duration)
        if end.hour > 17 or (end.hour == 17 and end.minute > 0):
            conflict('edited part exceeds workday')
        part['end'] = text(end)
        assigned = part['assignments'][:fields['cleaners_needed']]
        for assignment in assigned:
            if busy(state, assignment['cleaner_id'], instant(part['start']), instant(end), job['id']):
                conflict('edited job would overlap another booking or violate 1-hour spacing')
        if len(assigned) < fields['cleaners_needed']:
            candidates = free_at(state, instant(part['start']), instant(end), skip_job=job['id'])
            for cid in candidates:
                if cid not in [a['cleaner_id'] for a in assigned]:
                    assigned.append({'cleaner_id': cid, 'arrive': None, 'depart': None, 'extended_minutes': 0})
                    if len(assigned) == fields['cleaners_needed']:
                        break
            if len(assigned) != fields['cleaners_needed']:
                conflict('edited job lacks free cleaners at its booked time')
        part['assignments'] = assigned
    if len(durations) < len(parts):
        del parts[len(durations):]
    elif len(durations) > len(parts):
        extra = place(state, requested, durations[len(parts):], fields['cleaners_needed'],
                      start_day=day(parts[-1]['day']) + timedelta(days=1),
                      preferred=tuple(a['cleaner_id'] for a in parts[0]['assignments']))
        for new in extra:
            new['part_index'] = len(parts)
            parts.append(new)
    job.update({k: fields[k] for k in ('client_id', 'cleaners_needed', 'expected_length_hours', 'requested_day')})
    return job


def cascade(state, extended_job, part, assignment):
    """Rebook every later conflict as a unit. Transactions roll back on refusal."""
    cutoff = instant(part['end']) + timedelta(minutes=assignment['extended_minutes'] + 60)
    crew = {a['cleaner_id'] for a in part['assignments']}
    affected = []
    for job in state['jobs']:
        if job is extended_job or job['status'] != 'booked':
            continue
        if any(a['cleaner_id'] in crew and instant(p['start']) >= instant(part['start'])
               and instant(p['start']) < cutoff for p in job['parts'] for a in p['assignments']):
            if not future(job):
                conflict('cannot move an already arrived job')
            affected.append(job)
    affected.sort(key=lambda j: (j['parts'][0]['start'], j['id']))
    state['jobs'] = [j for j in state['jobs'] if j not in affected]
    for job in affected:
        job['parts'] = place(state, day(job['requested_day']),
                             lengths(job['expected_length_hours']), job['cleaners_needed'],
                             floor=cutoff.astimezone(ZONE).replace(tzinfo=None))
        state['jobs'].append(job)
    return [j['id'] for j in affected]
