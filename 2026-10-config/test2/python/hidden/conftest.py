"""Fixtures for testing the selected expense tracker through public interfaces."""
import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def target():
    value = os.environ.get("TARGET")
    if not value:
        pytest.fail("Set TARGET to the implementation repository root")
    path = Path(value).resolve()
    assert path.is_dir(), "TARGET must be a repository directory"
    return path


@pytest.fixture
def cli(target, tmp_path):
    def run(*args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(target)
        return subprocess.run(
            ["python3", "-m", "expenses", *map(str, args),
             "--file", str(tmp_path / "expenses.json")],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15,
        )
    return run


@pytest.fixture
def modules(target, monkeypatch):
    saved = {k: v for k, v in sys.modules.items()
             if k == "expenses" or k.startswith("expenses.")}
    for name in saved:
        del sys.modules[name]
    monkeypatch.syspath_prepend(str(target))
    yield lambda name: importlib.import_module("expenses." + name)
    for name in list(sys.modules):
        if name == "expenses" or name.startswith("expenses."):
            del sys.modules[name]
    sys.modules.update(saved)


@pytest.fixture
def web_request():
    from io import BytesIO
    from urllib.parse import urlencode, urlsplit
    from wsgiref.util import setup_testing_defaults

    def request(app, url="/", data=None):
        parts = urlsplit(url)
        env = {}
        setup_testing_defaults(env)
        body = urlencode(data).encode() if data is not None else b""
        env.update(PATH_INFO=parts.path, QUERY_STRING=parts.query,
                   REQUEST_METHOD="POST" if data is not None else "GET",
                   CONTENT_TYPE="application/x-www-form-urlencoded",
                   CONTENT_LENGTH=str(len(body)), **{"wsgi.input": BytesIO(body)})
        response = {}
        def start_response(status, headers, exc_info=None):
            response.update(status=int(status.split()[0]), headers=dict(headers))
        result = app(env, start_response)
        try:
            response["body"] = b"".join(result).decode("utf-8")
        finally:
            if hasattr(result, "close"):
                result.close()
        return response
    return request


@pytest.fixture
def web(modules, tmp_path, web_request):
    app = modules("web").make_app(str(tmp_path / "expenses.json"))
    return lambda url="/", data=None: web_request(app, url, data)


@pytest.fixture
def budget_web(modules, tmp_path, web_request):
    def make(budgets_path=None):
        kwargs = {} if budgets_path is None else {"budgets_path": str(budgets_path)}
        app = modules("web").make_app(str(tmp_path / "expenses.json"), **kwargs)
        return lambda url="/", data=None: web_request(app, url, data)
    return make
