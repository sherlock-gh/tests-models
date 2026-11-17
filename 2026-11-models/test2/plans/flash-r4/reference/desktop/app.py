"""Local back-office JSON API. create_app(path) is a callable WSGI test surface."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import make_server, WSGIServer
from cleaning.errors import AppError, bad, conflict, missing
from cleaning.store import Store, get, issue
from cleaning import scheduling, taps, invoices, utilization
from cleaning.timezone_util import day

ROOT = Path(__file__).resolve().parent


def integer(value, name):
    try:
        if isinstance(value, bool) or value is None or str(int(value)) != str(value):
            raise ValueError()
        return int(value)
    except (ValueError, TypeError):
        bad(f'{name} must be an integer')


def fields(body, names):
    if not isinstance(body, dict):
        bad('request body must be a JSON object')
    result = {}
    for name in names:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip():
            bad(f'{name} must be a non-empty string')
        result[name] = value
    return result


class DesktopApp:
    def __init__(self, data_file=None):
        self.store = Store(data_file or ROOT / 'data.json')

    def request(self, method, path, body=None):
        """Returns (HTTP status, JSON-compatible result), without network or thread setup."""
        try:
            return self._dispatch(method.upper(), path, body)
        except AppError as error:
            return error.status, {'error': error.message}
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            return 400, {'error': f'invalid request: {error}'}

    def _dispatch(self, method, url, body):
        parsed = urlsplit(url)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
        if path == '/' and method == 'GET':
            return 200, {'page': True}
        if not path.startswith('/api/'):
            missing('route does not exist')
        segments = path.strip('/').split('/')
        resource = segments[1]
        if resource in ('cleaners', 'clients'):
            names = ('name', 'phone', 'email') if resource == 'cleaners' else ('name', 'address', 'phone')
            if len(segments) == 2:
                if method == 'GET':
                    return 200, {resource: self.store.read()[resource]}
                if method == 'POST':
                    def create(state):
                        record = {'id': issue(state, resource), **fields(body, names)}
                        if resource == 'cleaners':
                            record['active'] = True
                        state[resource].append(record)
                        return record
                    return 201, {resource[:-1]: self.store.change(create)}
            if len(segments) == 3:
                identifier = integer(segments[2], 'id')
                if method == 'GET':
                    return 200, {resource[:-1]: get(self.store.read(), resource, identifier)}
                if method == 'PUT':
                    def update(state):
                        record = get(state, resource, identifier)
                        record.update(fields(body, names))
                        return record
                    return 200, {resource[:-1]: self.store.change(update)}
                if method == 'DELETE':
                    action = scheduling.delete_cleaner if resource == 'cleaners' else scheduling.delete_client
                    return 200, self.store.change(lambda state: action(state, identifier))
        if resource == 'jobs':
            if len(segments) == 2:
                if method == 'GET':
                    jobs = self.store.read()['jobs']
                    low = day(query['from']).isoformat() if 'from' in query else '0000-01-01'
                    high = day(query['to']).isoformat() if 'to' in query else '9999-12-31'
                    jobs = [j for j in jobs if any(low <= p['day'] <= high for p in j['parts'])]
                    if 'client_id' in query:
                        cid = integer(query['client_id'], 'client_id')
                        jobs = [j for j in jobs if j['client_id'] == cid]
                    return 200, {'jobs': jobs}
                if method == 'POST':
                    return 201, {'job': self.store.change(lambda s: scheduling.book(s, body))}
            if len(segments) == 3:
                jid = integer(segments[2], 'id')
                if method == 'GET':
                    return 200, {'job': get(self.store.read(), 'jobs', jid)}
                if method == 'PUT':
                    return 200, {'job': self.store.change(lambda s: scheduling.edit(s, get(s, 'jobs', jid), body))}
                if method == 'DELETE':
                    def delete(state):
                        job = get(state, 'jobs', jid)
                        if job['invoice_id'] is not None:
                            conflict('invoice issued; cannot delete job')
                        state['jobs'].remove(job)
                        return {'ok': True}
                    return 200, self.store.change(delete)
        if resource == 'invoices':
            if len(segments) == 2 and method == 'GET':
                records = self.store.read()['invoices']
                if 'settled' in query:
                    if query['settled'] not in ('true', 'false'):
                        bad('settled must be true or false')
                    records = [i for i in records if i['settled'] == (query['settled'] == 'true')]
                return 200, {'invoices': records}
            if len(segments) >= 3:
                iid = integer(segments[2], 'id')
                if len(segments) == 3 and method == 'GET':
                    return 200, {'invoice': get(self.store.read(), 'invoices', iid)}
                if len(segments) == 4 and segments[3] == 'payment' and method == 'POST':
                    amount = body.get('amount_cents') if isinstance(body, dict) else None
                    return 200, {'invoice': self.store.change(lambda s: invoices.record_payment(s, iid, amount))}
        if resource == 'assignments' and method == 'POST' and len(segments) == 3:
            if segments[2] == 'tap':
                return 200, {'job': self.store.change(lambda s: taps.tap(s, body))}
            if segments[2] == 'extend':
                return 200, self.store.change(lambda s: taps.extend(s, body))
        if resource == 'day' and method == 'GET' and len(segments) == 2:
            return 200, taps.day_schedule(self.store.read(), integer(query.get('cleaner_id'), 'cleaner_id'), query.get('on'))
        if resource == 'utilization' and method == 'GET' and len(segments) == 2:
            return 200, utilization.utilization(self.store.read(), integer(query.get('cleaner_id'), 'cleaner_id'), query.get('from'), query.get('to'))
        missing('route does not exist')

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        if method == 'GET' and path == '/':
            page = (ROOT / 'static' / 'index.html').read_bytes()
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(page)))])
            return [page]
        try:
            size = int(environ.get('CONTENT_LENGTH') or 0)
            if size < 0 or size > 1024 * 1024:
                bad('invalid body length')
            raw = environ['wsgi.input'].read(size) if size else b''
            body = json.loads(raw.decode('utf-8')) if raw else None
            status, result = self.request(method, path + ('?' + environ['QUERY_STRING'] if environ.get('QUERY_STRING') else ''), body)
        except (ValueError, UnicodeError, AppError) as error:
            status, result = 400, {'error': str(error)}
        output = json.dumps(result).encode('utf-8')
        reason = {200: 'OK', 201: 'Created', 400: 'Bad Request', 404: 'Not Found', 409: 'Conflict'}[status]
        start_response(f'{status} {reason}', [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(output)))])
        return [output]


def create_app(data_file=None):
    return DesktopApp(data_file)


application = create_app()
app = application


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '18080'))
    with make_server('127.0.0.1', port, application) as server:
        print(f'Serving http://127.0.0.1:{port}', flush=True)
        server.serve_forever()
