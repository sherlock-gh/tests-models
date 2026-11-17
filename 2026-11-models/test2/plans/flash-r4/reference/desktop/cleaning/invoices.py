"""Invoice snapshot and settlement."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from .errors import bad, conflict
from .models import worked_minutes
from .store import get, issue
from .timezone_util import ZONE, text


def issue_invoice(state, job, at):
    if job['invoice_id'] is not None:
        return get(state, 'invoices', job['invoice_id'])
    cleaners = sorted({a['cleaner_id'] for p in job['parts'] for a in p['assignments']})
    lines = []
    for cid in cleaners:
        cleaner = next((c for c in state['cleaners'] if c['id'] == cid), None)
        minutes = worked_minutes(job, cid)
        amount = int((Decimal(minutes) * 4500 / 60).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        lines.append({'cleaner_id': cid, 'cleaner_name': cleaner['name'] if cleaner else f'Cleaner {cid}',
                      'minutes_worked': minutes, 'amount_cents': amount})
    invoice = {'id': issue(state, 'invoices'), 'job_id': job['id'], 'issued_at': at,
               'lines': lines, 'total_cents': sum(line['amount_cents'] for line in lines),
               'settled': False, 'payment': None}
    state['invoices'].append(invoice)
    job['invoice_id'] = invoice['id']
    return invoice


def record_payment(state, invoice_id, amount):
    invoice = get(state, 'invoices', invoice_id)
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        bad('amount_cents must be a nonnegative integer')
    if invoice['settled']:
        conflict('invoice already settled')
    if amount != invoice['total_cents']:
        conflict('payment must equal total exactly')
    invoice['settled'] = True
    invoice['payment'] = {'amount_cents': amount, 'paid_at': text(datetime.now(ZONE))}
    return invoice
