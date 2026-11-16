"""Back office (Flash-Next's plan, contracts/backoffice-web.md and exact-interfaces.md), standard library only:
PORT=18080 STORE=webapp/data/store.json python3 webapp/app.py"""
import html
import json
import os
import re
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cleaning import core  # noqa: E402
from cleaning.core import Refused  # noqa: E402

STORE = core.Store(os.environ.get("STORE", "webapp/data/store.json"))


def now():
    return datetime.now().strftime(core.FMT)


def f(form, k, default=None):
    return form.get(k, [default])[0]


ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile(pattern + "$"), fn))
        return fn
    return deco


@route("GET", r"/")
def _(q, form): return {"links": ["/cleaners", "/clients", "/jobs", "/invoices", "/utilization"]}
@route("GET", r"/cleaners")
def _(q, form): return STORE.read(lambda s: s["cleaners"])
@route("POST", r"/cleaners")
def _(q, form): return STORE.run(core.add_person, "cleaners", f(form, "name"))
@route("GET", r"/cleaners/(\d+)")
def _(q, form, i): return STORE.read(core.find, "cleaners", i)
@route("POST", r"/cleaners/(\d+)")
def _(q, form, i): return STORE.run(core.update_person, "cleaners", i, f(form, "name"))
@route("POST", r"/cleaners/(\d+)/delete")
def _(q, form, i): return STORE.run(core.delete_cleaner, i)
@route("GET", r"/clients")
def _(q, form): return STORE.read(lambda s: s["clients"])
@route("POST", r"/clients")
def _(q, form): return STORE.run(core.add_person, "clients", f(form, "name"))
@route("GET", r"/clients/(\d+)")
def _(q, form, i): return STORE.read(core.find, "clients", i)
@route("POST", r"/clients/(\d+)")
def _(q, form, i): return STORE.run(core.update_person, "clients", i, f(form, "name"))
@route("POST", r"/clients/(\d+)/delete")
def _(q, form, i): return STORE.run(core.delete_client, i)
@route("POST", r"/jobs/book")
def _(q, form): return STORE.run(core.book, f(form, "client_id"), f(form, "cleaners_required"), f(form, "hours"), f(form, "requested_day"))
@route("GET", r"/jobs")
def _(q, form): return STORE.read(lambda s: s["jobs"])
@route("GET", r"/jobs/(\d+)")
def _(q, form, i): return STORE.read(core.find, "jobs", i)
@route("GET", r"/jobs/(\d+)/edit")
def _(q, form, i): return STORE.read(core.find, "jobs", i)
@route("POST", r"/jobs/(\d+)")
def _(q, form, i): return STORE.run(core.edit_job, i, f(form, "client_id"), f(form, "cleaners_required"), f(form, "hours"))
@route("POST", r"/jobs/(\d+)/delete")
def _(q, form, i): return STORE.run(core.delete_job, i)
@route("GET", r"/invoices")
def _(q, form): return STORE.read(lambda s: s["invoices"])
@route("GET", r"/invoices/(\d+)")
def _(q, form, i): return STORE.read(core.find, "invoices", i)
@route("POST", r"/invoices/(\d+)/pay")
def _(q, form, i): return STORE.run(core.pay, i, f(form, "amount"), now())
@route("GET", r"/utilization")
def _(q, form): return STORE.read(core.utilization, f(q, "day", date.today().isoformat()))
@route("GET", r"/field/(\d+)/today")
def _(q, form, c): return STORE.read(core.cleaner_day, c, f(q, "day", date.today().isoformat()))
@route("POST", r"/field/(\d+)/jobs/(\d+)/arrive")
def _(q, form, c, j): return STORE.run(core.arrive, c, j, f(form, "at") or now())
@route("POST", r"/field/(\d+)/jobs/(\d+)/depart")
def _(q, form, c, j): return STORE.run(core.depart, c, j, f(form, "at") or now())
@route("POST", r"/field/(\d+)/jobs/(\d+)/extend")
def _(q, form, c, j): return STORE.run(core.extend, c, j)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def answer(self, out):
        if "application/json" in (self.headers.get("Accept") or ""):
            body, ctype = json.dumps(out).encode(), "application/json"
        else:
            body = f"<!doctype html><html><body><h1>Back office</h1><pre>{html.escape(json.dumps(out, indent=1))}</pre></body></html>".encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_any(self, method):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode()) if n else {}
        for m, rx, fn in ROUTES:
            hit = rx.match(u.path)
            if m == method and hit:
                try:
                    return self.answer(fn(parse_qs(u.query), form, *hit.groups()))
                except Refused as e:
                    return self.answer({"error": {"code": e.code, "message": e.message}})
        self.answer({"error": {"code": "not_found", "message": f"no page {u.path}"}})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(os.environ.get("PORT", "18080"))), Handler).serve_forever()
