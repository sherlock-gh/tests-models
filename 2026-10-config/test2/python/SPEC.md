# Expense tracker: specification

A small personal expense tracker: a Python package with a command line and a web interface.

## Ground rules

- Python 3 standard library only; nothing can be installed. Tests use pytest.
- Package `expenses/` (with `__init__.py`); tests in `tests/`.
- `python3 -m pytest -q` must pass.
- Never commit data files: `expenses.json` and `budgets.json` go in `.gitignore`.

## 1. Model and store

- `expenses/models.py`: dataclass `Expense(date: datetime.date, amount_cents: int, category: str, note: str = "")`.
- `expenses/store.py`: JSON-file store `Store(path)` with `add(expense) -> int` (returns a new integer id), `list() -> list of (id, Expense)` in date order, and load/save to the JSON file (a missing file is an empty store). `add` saves at once, so a new `Store(path)` on the same file lists what was added.
- Tests in `tests/test_store.py`: add, list order, save/load round trip (tmp_path).

## 2. Command line

`python -m expenses` (`expenses/__main__.py` calling `expenses/cli.py` `main(argv=None, out=sys.stdout) -> int`). Default data file: `./expenses.json`.

- `add --date YYYY-MM-DD --amount 12.34 --category food [--note text] [--file path]`
- `list [--file path]`: one line per expense: id, date, amount with 2 decimals, category, note.
- Invalid date or amount: error message on stderr, exit code 2.
- Tests in `tests/test_cli.py` call `main()` with tmp_path files and capture output.

## 3. Monthly summary

`summary --month YYYY-MM [--file path]`: total per category for that month, sorted by total descending, then a `TOTAL` line; amounts with 2 decimals. A month with no expenses prints `no expenses`. The calculation lives in `expenses/report.py` as a pure function. Tests for the function and the command.

## 4. CSV import

`import-csv PATH [--file path]`: imports expenses from a CSV with header `date,amount,category,note`, using the csv module. Validate every row first; if any row is invalid, import nothing, print each bad row's line number and reason to stderr, and exit 2. On success print how many were imported. Tests with good and bad CSV files, including a note containing a comma and quotes.

## 5. Budgets

Monthly budgets per category from a JSON file (default `./budgets.json`, e.g. `{"food": 400.00}`). `report --month YYYY-MM [--file path] [--budgets path]` prints the summary from the summary command plus, for each category with a budget, the budget, the amount spent, and `OVER` or `ok`; categories without a budget are listed as `no budget`. Reuses `expenses/report.py`. Tests.

## 6. Web UI

`expenses/web.py`: WSGI app `make_app(store_path)`. Escape user text with `html.escape`; inline CSS only, no JavaScript, no external resources. Reuse the CLI/store/report code; don't duplicate validation or calculations. Tests call the WSGI app directly with environ dicts (`wsgiref.util.setup_testing_defaults`) and never open sockets; they go in `tests/test_web.py`.

- `serve [--host 127.0.0.1] [--port 8000] [--file path]` CLI command runs `make_app` with `wsgiref.simple_server`.
- `GET /`: all expenses as an HTML table (date, amount with 2 decimals, category, note) plus the total, and links to `/add`, `/summary` and `/import`. Unknown paths return 404. Tests: empty store, one expense, escaping of a note containing `<b>`, a 404.
- `GET /add`: form (date, amount, category, note). `POST /add`: validated exactly as the CLI `add` command (reuse its parsing). Invalid input: the form again with the error and the user's values, status 400. Success: save, then 303 redirect to `/`. Tests: a bad date, a bad amount, a good add followed by the list page showing it.
- `GET /summary?month=YYYY-MM`: per-category totals for the month from `expenses/report.py`, sorted as the CLI summary sorts them, with a `TOTAL` row, a month input (`type=month`) defaulting to the current month, and `no expenses` for an empty month. Invalid month: a message and status 400. Tests: a month with data, an empty month, a bad month.
- `GET /import`: a textarea for pasting CSV with header `date,amount,category,note`. `POST /import`: reuses the CLI import-csv validation; all-or-nothing; if any row is bad, show each bad line number and reason (status 400), otherwise show how many were imported. Tests: a good paste (including a note with a comma and quotes) and a bad one.
- `GET /budgets?month=YYYY-MM`: the budget report for the month, the same data as the CLI `report` command and computed by the same code in `expenses/report.py`: each category with a budget shows the budget, the amount spent and `OVER` or `ok`; categories with spending but no budget show `no budget`. A month input (`type=month`) defaults to the current month; an invalid month gives a message and status 400. The page also has a form to set one category's budget (category, amount). `POST /budgets` validates the amount as the CLI does (reuse its parsing), saves it to the budgets file, and redirects with 303 to `/budgets`; invalid input gives a message and status 400. The budgets file is passed in as `make_app(store_path, budgets_path="budgets.json")`, and `serve` takes `[--budgets path]` (default `./budgets.json`). `/` links to `/budgets`. Tests: a month with one category over budget and one ok, a category without a budget, setting a budget, a bad amount.

## 7. Polish

Type hints, a short docstring in every module, and a `README.md` explaining installation-free usage (`python -m expenses ...`) with an example for every command and a "Web UI" section (the `serve` command and what each page does).
