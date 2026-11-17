# Desktop reference tests

Run `python3 -m unittest discover -s tests -v` or `python3 -m pytest -q tests` from `desktop/`. Tests drive the WSGI handler in-process; no loopback port or external network is required. The public test seam is `from app import create_app`; construct with a temporary JSON path, then use `app(environ, start_response)` or `app.request(method, path, body)`.
