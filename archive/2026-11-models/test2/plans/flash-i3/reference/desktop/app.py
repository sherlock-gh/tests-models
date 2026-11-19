"""The back office's WSGI app: the page at / and the JSON API of contracts/desktop-api.md.
Every request loads the data file, works on that copy, and rewrites the file only on success."""
import json
import os
import re
from datetime import timedelta
from pathlib import Path

from . import rules
from .rules import RuleError

HERE = Path(__file__).resolve().parent


def data_path():
    return Path(os.environ.get("CLEANING_DATA") or HERE / "data.json")


def load():
    p = data_path()
    if not p.exists():
        return {"cleaners": [], "clients": [], "jobs": [], "invoices": [], "payments": [], "seq": {}}
    try:
        return json.loads(p.read_text())
    except ValueError:
        raise RuleError(f"the data file {p} can't be read; nothing was changed")


def save(doc):
    p = data_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1))
    os.replace(tmp, p)


def job_out(doc, j):
    names = {c["id"]: c["name"] for c in doc["clients"]}
    parts = []
    for p in j["parts"]:
        s, e = rules.part_span(p)
        parts.append({"start_day": p["start_day"], "start": rules.fmt(s), "end": rules.fmt(e), "duration_min": p["end_min"] - p["start_min"]})
    return {"id": j["id"], "client_id": j["client_id"], "client_name": names.get(j["client_id"]),
            "cleaners_needed": j["cleaners_needed"], "expected_length_min": j["expected_length_min"],
            "requested_day": j["requested_day"], "cleaner_ids": list(j["cleaner_ids"]), "status": j["status"],
            "parts": parts, "invoice_id": j["invoice_id"], "taps": [dict(t) for t in j["taps"]]}


def money(cents):
    return f"${cents // 100}.{cents % 100:02d}"


def invoice_out(doc, inv):
    names = {c["id"]: c["name"] for c in doc["cleaners"]}
    return {"id": inv["id"], "job_id": inv["job_id"], "issued_at": inv["issued_at"],
            "lines": [{"cleaner_id": l["cleaner_id"], "cleaner_name": names.get(l["cleaner_id"]), "minutes_worked": l["minutes_worked"],
                       "cents": l["cents"], "amount_str": money(l["cents"])} for l in inv["lines"]],
            "total_cents": inv["total_cents"], "total_str": money(inv["total_cents"]), "settled": rules.settled(doc, inv)}


def name_of(body):
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RuleError("a name is required")
    return name.strip()


def records(kind):
    def create(doc, body):
        r = {"id": rules.next_id(doc, kind), "name": name_of(body)}
        doc[kind].append(r)
        return 201, dict(r), True

    def lst(doc, body):
        return 200, {kind: [dict(r) for r in doc[kind]]}, False

    def get(doc, body, rid):
        return 200, dict(rules.find(doc, kind, rid)), False

    def put(doc, body, rid):
        r = rules.find(doc, kind, rid)
        r["name"] = name_of(body)
        return 200, dict(r), True

    def delete(doc, body, rid):
        (rules.delete_cleaner if kind == "cleaners" else rules.delete_client)(doc, rid)
        return 200, {"ok": True}, True
    return create, lst, get, put, delete


def jobs_list(doc, body):
    return 200, {"jobs": [job_out(doc, j) for j in doc["jobs"]]}, False


def jobs_create(doc, body):
    return 201, job_out(doc, rules.book(doc, body)), True


def job_get(doc, body, jid):
    return 200, job_out(doc, rules.find(doc, "jobs", jid)), False


def job_put(doc, body, jid):
    return 200, job_out(doc, rules.update_job(doc, jid, body)), True


def job_delete(doc, body, jid):
    rules.delete_job(doc, jid)
    return 200, {"ok": True}, True


def today(doc, body, query):
    day = rules.parse_day(query.get("date"))
    try:
        cid = int(query.get("cleaner_id"))
    except (TypeError, ValueError):
        raise RuleError("cleaner_id is required")
    rules.find(doc, "cleaners", cid)
    hits = []
    for j in doc["jobs"]:
        if j["status"] == "cancelled" or cid not in j["cleaner_ids"]:
            continue
        for p in j["parts"]:
            if p["start_day"] == day.isoformat():
                hits.append((p["start_min"], j["id"], j))
                break
    return 200, {"jobs": [job_out(doc, j) for _, _, j in sorted(hits)]}, False


def arrive(doc, body, jid):
    return 200, job_out(doc, rules.arrive(doc, jid, body)), True


def depart(doc, body, jid):
    job, inv = rules.depart(doc, jid, body)
    out = job_out(doc, job)
    if inv is not None:
        out["invoice"] = invoice_out(doc, inv)
    return 200, out, True


def more_time(doc, body, jid):
    job, moved = rules.more_time(doc, jid, body)
    out = job_out(doc, job)
    out["rebooked"] = [{"job_id": m, "parts": job_out(doc, rules.find(doc, "jobs", m))["parts"]} for m in moved]
    return 200, out, True


def invoices(doc, body):
    return 200, {"invoices": [invoice_out(doc, i) for i in doc["invoices"]]}, False


def invoice_get(doc, body, iid):
    return 200, invoice_out(doc, rules.find(doc, "invoices", iid)), False


def invoice_pay(doc, body, iid):
    return 200, invoice_out(doc, rules.pay(doc, iid, body)), True


def invoice_locked(doc, body, iid=None):
    raise RuleError("issued invoices never change and are never deleted")


def util_daily(doc, body, query):
    d = rules.parse_day(query.get("date"))
    return 200, {"entries": rules.utilization(doc, [d], 8)}, False


def util_weekly(doc, body, query):
    d = rules.parse_day(query.get("week_start"))
    return 200, {"entries": rules.utilization(doc, [d + timedelta(days=i) for i in range(7)], 40)}, False


cc, cl, cg, cp, cd = records("cleaners")
kc, kl, kg, kp, kd = records("clients")
ROUTES = [  # method, pattern, handler, takes the query
    ("GET", r"/api/cleaners", cl, False), ("POST", r"/api/cleaners", cc, False),
    ("GET", r"/api/cleaners/(\d+)", cg, False), ("PUT", r"/api/cleaners/(\d+)", cp, False), ("DELETE", r"/api/cleaners/(\d+)", cd, False),
    ("GET", r"/api/clients", kl, False), ("POST", r"/api/clients", kc, False),
    ("GET", r"/api/clients/(\d+)", kg, False), ("PUT", r"/api/clients/(\d+)", kp, False), ("DELETE", r"/api/clients/(\d+)", kd, False),
    ("GET", r"/api/jobs/today", today, True),
    ("GET", r"/api/jobs", jobs_list, False), ("POST", r"/api/jobs", jobs_create, False),
    ("GET", r"/api/jobs/(\d+)", job_get, False), ("PUT", r"/api/jobs/(\d+)", job_put, False), ("DELETE", r"/api/jobs/(\d+)", job_delete, False),
    ("POST", r"/api/jobs/(\d+)/arrive", arrive, False), ("POST", r"/api/jobs/(\d+)/depart", depart, False),
    ("POST", r"/api/jobs/(\d+)/more-time", more_time, False),
    ("GET", r"/api/invoices", invoices, False), ("GET", r"/api/invoices/(\d+)", invoice_get, False),
    ("POST", r"/api/invoices/(\d+)/pay", invoice_pay, False),
    ("PUT", r"/api/invoices(?:/(\d+))?", invoice_locked, False), ("DELETE", r"/api/invoices(?:/(\d+))?", invoice_locked, False),
    ("GET", r"/api/utilization/daily", util_daily, True), ("GET", r"/api/utilization/weekly", util_weekly, True),
]


def handle(method, path, query, raw):
    if method == "GET" and path in ("/", "/index.html"):
        return 200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8"
    for m, pat, fn, takes_query in ROUTES:
        hit = re.fullmatch(pat, path)
        if hit and m == method:
            break
    else:
        return 404, {"error": f"no route {method} {path}"}, None
    try:
        body = json.loads(raw) if raw.strip() else {}
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return 400, {"error": "the request body must be a JSON object"}, None
    try:
        doc = load()
        args = [int(g) for g in hit.groups() if g is not None]
        status, out, changed = fn(doc, body, query) if takes_query else fn(doc, body, *args)
        if changed:
            save(doc)
        return status, out, None
    except RuleError as e:
        return e.status, {"error": e.message}, None
    except Exception as e:   # never stop the app, never write half a change
        return 400, {"error": f"the request failed: {e}"}, None


def app(environ, start_response):
    from urllib.parse import parse_qs
    method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
    query = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
    try:
        n = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        n = 0
    raw = environ["wsgi.input"].read(n).decode("utf-8", "replace") if n else ""
    status, out, ctype = handle(method, path, query, raw)
    body = out if isinstance(out, bytes) else json.dumps(out).encode()
    reason = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found"}[status]
    start_response(f"{status} {reason}", [("Content-Type", ctype or "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]
