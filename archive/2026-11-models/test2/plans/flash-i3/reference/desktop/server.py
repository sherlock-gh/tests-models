"""`python -m desktop.server`: serves the back office on 127.0.0.1:$PORT (default 18080)."""
import os
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .app import app


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


def main():
    port = int(os.environ.get("PORT") or 18080)
    with make_server("127.0.0.1", port, app, server_class=Server, handler_class=Quiet) as s:
        s.serve_forever()


if __name__ == "__main__":
    main()
