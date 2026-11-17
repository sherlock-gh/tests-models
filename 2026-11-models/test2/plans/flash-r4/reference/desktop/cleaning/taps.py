"""Per-part taps, day view and extensions."""
from .errors import bad, conflict, missing
from .store import get
from .timezone_util import clock, day, instant
from .invoices import issue_invoice
from .scheduling import cascade


def find_assignment(job, cid, at=None):
    matches = [(p, a) for p in job['parts'] for a in p['assignments'] if a['cleaner_id'] == cid]
    if not matches:
        missing(f'cleaner {cid} is not assigned to job {job["id"]}')
    if at is not None:
        on = clock(at).date().isoformat()
        today = [(p, a) for p, a in matches if p['day'] == on]
        if today:
            return today[0]
    # For split jobs, choose the first assignment still actionable.
    return next(((p, a) for p, a in matches if a['depart'] is None), matches[-1])


def tap(state, fields):
    if not isinstance(fields, dict):
        bad('tap body must be an object')
    jid, cid, kind, at = (fields.get(k) for k in ('job_id', 'cleaner_id', 'kind', 'at'))
    if isinstance(jid, bool) or not isinstance(jid, int) or isinstance(cid, bool) or not isinstance(cid, int):
        bad('job_id and cleaner_id must be integers')
    if kind not in ('arrive', 'depart'):
        bad('kind must be arrive or depart')
    clock(at)
    job = get(state, 'jobs', jid)
    if job['status'] != 'booked':
        conflict('cancelled job cannot be tapped')
    part, assignment = find_assignment(job, cid, at)
    if kind == 'arrive':
        if assignment['arrive'] is not None:
            conflict('already arrived')
        assignment['arrive'] = at
    else:
        if assignment['arrive'] is None:
            conflict('depart requires arrive')
        if assignment['depart'] is not None:
            conflict('already departed')
        if instant(at) < instant(assignment['arrive']):
            conflict('depart before arrive')
        assignment['depart'] = at
        if job['invoice_id'] is None and all(a['depart'] is not None for p in job['parts'] for a in p['assignments']):
            issue_invoice(state, job, at)
    return job


def extend(state, fields):
    if not isinstance(fields, dict):
        bad('extension body must be an object')
    jid, cid, minutes, at = (fields.get(k) for k in ('job_id', 'cleaner_id', 'minutes', 'at'))
    if isinstance(jid, bool) or not isinstance(jid, int) or isinstance(cid, bool) or not isinstance(cid, int):
        bad('job_id and cleaner_id must be integers')
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes != 20:
        bad('extension must be a 20-minute step')
    clock(at)
    job = get(state, 'jobs', jid)
    part, assignment = find_assignment(job, cid, at)
    if job['status'] != 'booked' or assignment['arrive'] is None or assignment['depart'] is not None:
        conflict('extend requires arrived cleaner not yet departed')
    if instant(at) < instant(assignment['arrive']):
        conflict('extension before arrival')
    assignment['extended_minutes'] += minutes
    bumped = cascade(state, job, part, assignment)
    return {'job': job, 'rebooked_job_ids': bumped}


def day_schedule(state, cid, on):
    get(state, 'cleaners', cid)
    date = day(on).isoformat()
    parts = []
    for job in state['jobs']:
        if job['status'] != 'booked':
            continue
        for part in job['parts']:
            if part['day'] == date and any(a['cleaner_id'] == cid for a in part['assignments']):
                view = dict(part)
                view.update({'job_id': job['id'], 'client_id': job['client_id'],
                             'client': next((c for c in state['clients'] if c['id'] == job['client_id']), None),
                             'co_workers': [a['cleaner_id'] for a in part['assignments'] if a['cleaner_id'] != cid]})
                parts.append(view)
    return {'parts': sorted(parts, key=lambda p: (p['start'], p['job_id']))}
