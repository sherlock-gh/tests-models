"""Local HTTP/JSON API (contracts/http-api.md, interfaces.md): python3 -m desktop.cleaning.server --data PATH --port N"""
import argparse
import json
import re
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import CleaningError, Service

STATUS = {"invalid_input": 400, "not_found": 404, "unschedulable": 409, "invalid_state": 409, "payment_mismatch": 409}
STATIC = Path(__file__).parent / "static"


def make_handler(svc):
    routes = []

    def route(method, pattern):
        def deco(fn):
            routes.append((method, re.compile(pattern + "$"), fn))
            return fn
        return deco

    @route("GET", r"/api/cleaners")
    def _(b, q): return 200, svc.list_cleaners()

    @route("POST", r"/api/cleaners")
    def _(b, q): return 201, svc.create_cleaner(b.get("name"))

    @route("GET", r"/api/cleaners/(\d+)")
    def _(b, q, i): return 200, svc.get_cleaner(int(i))

    @route("PUT", r"/api/cleaners/(\d+)")
    def _(b, q, i): return 200, svc.update_cleaner(int(i), b.get("name"))

    @route("DELETE", r"/api/cleaners/(\d+)")
    def _(b, q, i): return 204, svc.delete_cleaner(int(i))

    @route("GET", r"/api/cleaners/(\d+)/day")
    def _(b, q, i): return 200, svc.cleaner_day(int(i), q.get("date", [None])[0])

    @route("GET", r"/api/clients")
    def _(b, q): return 200, svc.list_clients()

    @route("POST", r"/api/clients")
    def _(b, q): return 201, svc.create_client(b.get("name"), b.get("address"))

    @route("GET", r"/api/clients/(\d+)")
    def _(b, q, i): return 200, svc.get_client(int(i))

    @route("PUT", r"/api/clients/(\d+)")
    def _(b, q, i): return 200, svc.update_client(int(i), b.get("name"), b.get("address"))

    @route("DELETE", r"/api/clients/(\d+)")
    def _(b, q, i): return 204, svc.delete_client(int(i))

    @route("GET", r"/api/jobs")
    def _(b, q): return 200, svc.list_jobs()

    @route("POST", r"/api/jobs")
    def _(b, q): return 201, svc.book_job(b.get("clientId"), b.get("cleanersNeeded"), b.get("lengthMinutes"), b.get("requestedDate"))

    @route("GET", r"/api/jobs/(\d+)")
    def _(b, q, i): return 200, svc.get_job(int(i))

    @route("PUT", r"/api/jobs/(\d+)")
    def _(b, q, i): return 200, svc.update_job(int(i), b.get("clientId"), b.get("cleanersNeeded"), b.get("lengthMinutes"), b.get("requestedDate"))

    @route("DELETE", r"/api/jobs/(\d+)")
    def _(b, q, i): return 204, svc.delete_job(int(i))

    @route("POST", r"/api/jobs/(\d+)/arrive")
    def _(b, q, i): return 200, svc.arrive(int(i), b.get("cleanerId"), b.get("timestamp"))

    @route("POST", r"/api/jobs/(\d+)/depart")
    def _(b, q, i): return 200, svc.depart(int(i), b.get("cleanerId"), b.get("timestamp"))

    @route("POST", r"/api/jobs/(\d+)/extend")
    def _(b, q, i): return 200, svc.request_extension(int(i), b.get("cleanerId"), b.get("minutes"))

    @route("GET", r"/api/invoices")
    def _(b, q):
        s = q.get("settled", [None])[0]
        return 200, svc.list_invoices(None if s is None else s == "true")

    @route("GET", r"/api/invoices/(\d+)")
    def _(b, q, i): return 200, svc.get_invoice(int(i))

    @route("POST", r"/api/invoices/(\d+)/pay")
    def _(b, q, i): return 200, svc.pay_invoice(int(i), b.get("amountCents"))

    @route("GET", r"/api/utilization")
    def _(b, q): return 200, svc.utilization(q.get("date", [None])[0])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def handle_any(self, method):
            u = urlparse(self.path)
            if method == "GET" and u.path in ("/", "/index.html"):
                return self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            for m, rx, fn in routes:
                hit = rx.match(u.path)
                if m == method and hit:
                    try:
                        n = int(self.headers.get("Content-Length") or 0)
                        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
                        if not isinstance(body, dict):
                            raise CleaningError("invalid_input", "the body must be a JSON object")
                        code, out = fn(body, parse_qs(u.query), *hit.groups())
                        return self.send(code, None if code == 204 else out)
                    except CleaningError as e:
                        return self.send(STATUS[e.code], {"error": {"code": e.code, "message": e.message}})
                    except json.JSONDecodeError:
                        return self.send(400, {"error": {"code": "invalid_input", "message": "the body is not JSON"}})
                    except Exception as e:  # never exits; data unchanged (operations commit last)
                        traceback.print_exc()
                        return self.send(500, {"error": {"code": "internal", "message": str(e)}})
            self.send(404, {"error": {"code": "not_found", "message": f"no route {method} {u.path}"}})

        def do_GET(self): self.handle_any("GET")
        def do_POST(self): self.handle_any("POST")
        def do_PUT(self): self.handle_any("PUT")
        def do_DELETE(self): self.handle_any("DELETE")

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/desktop.json")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    HTTPServer(("127.0.0.1", a.port), make_handler(Service(a.data))).serve_forever()


if __name__ == "__main__":
    main()
