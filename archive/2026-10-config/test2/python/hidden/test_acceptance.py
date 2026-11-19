"""Black-box acceptance coverage derived solely from SPEC.md."""
import ast
import csv
import datetime as dt
from dataclasses import is_dataclass
from html.parser import HTMLParser
import io
import re

import pytest


class Page(HTMLParser):
    """Extract visible text and semantic elements without depending on layout."""
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.tags = []
        self.rows = []
        self.row = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "tr":
            self.row = []

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows.append(" ".join(self.row))
            self.row = None

    def handle_data(self, data):
        self.text.append(data)
        if self.row is not None:
            self.row.append(data)

    @property
    def visible(self):
        return " ".join(self.text)


def success(result):
    assert result.returncode == 0, result.stderr
    return result.stdout


def add(cli, date="2024-02-10", amount="12.34", category="food", note=""):
    return success(cli("add", "--date", date, "--amount", amount,
                       "--category", category, "--note", note))


def seeded(cli):
    add(cli, amount="10.00", category="food")
    add(cli, date="2024-02-11", amount="2.50", category="food")
    add(cli, amount="20.00", category="travel")
    add(cli, date="2024-03-01", amount="99.00", category="other")


def amount(text, value):
    assert re.search(r"(?<![\d.])" + re.escape(value) + r"(?![\d.])", text), text


def summary(text):
    assert text.index("travel") < text.index("food") < text.index("TOTAL")
    amount(text, "20.00")
    amount(text, "12.50")
    amount(text, "32.50")
    assert "other" not in text


def csv_text(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["date", "amount", "category", "note"])
    writer.writerows(rows)
    return stream.getvalue()


def bad_rows():
    return [("2024-02-01", "1.00", "valid", ""),
            ("2024-02-30", "2.00", "bad-date", ""),
            ("2024-02-02", "garbage", "bad-amount", "")]


def line_numbers(text):
    # Accept arbitrary error wording; both offending physical CSV lines must appear.
    for number in (3, 4):
        assert re.search(r"\b" + str(number) + r"\b", text), text
    assert re.search(r"[A-Za-z]", text), "Expected a reason as well as line numbers"


def test_model_contract(modules):
    """Section 1: Expense dataclass fields and default note."""
    cls = modules("models").Expense
    assert is_dataclass(cls)
    expense = cls(dt.date(2024, 2, 1), 1234, "food")
    assert (expense.date, expense.amount_cents, expense.category, expense.note) == (
        dt.date(2024, 2, 1), 1234, "food", "")


def test_missing_store(modules, tmp_path):
    """Section 1: A missing data file represents an empty store."""
    assert modules("store").Store(tmp_path / "absent.json").list() == []


def test_store_order_and_roundtrip(modules, tmp_path):
    """Section 1: Unique integer IDs, date ordering, and persistent round trip."""
    cls = modules("models").Expense
    store_cls = modules("store").Store
    path = tmp_path / "store.json"
    store = store_cls(path)
    later = cls(dt.date(2024, 2, 20), 1234, "food", 'comma, and "quote"')
    earlier = cls(dt.date(2024, 1, 1), 99, "travel")
    ids = [store.add(later), store.add(earlier)]
    assert all(isinstance(i, int) for i in ids) and ids[0] != ids[1]
    expected = [(ids[1], earlier), (ids[0], later)]
    assert store.list() == expected
    assert store_cls(path).list() == expected


def test_cli_add_list_order(cli):
    """Section 2: Add/list fields, two decimals, and date order."""
    add(cli, date="2024-02-20", note='lunch, "shared"')
    add(cli, date="2024-01-01", amount="2", category="travel")
    lines = [line for line in success(cli("list")).splitlines() if line.strip()]
    early = next(line for line in lines if "2024-01-01" in line)
    late = next(line for line in lines if "2024-02-20" in line)
    assert lines.index(early) < lines.index(late)
    amount(early, "2.00")
    amount(late, "12.34")
    assert "travel" in early and "food" in late and 'lunch, "shared"' in late
    for line, date in [(early, "2024-01-01"), (late, "2024-02-20")]:
        assert re.search(r"\b\d+\b", line.split(date)[0]), "Missing ID"


@pytest.mark.parametrize("date,value", [("2024-02-30", "1.00"),
                                         ("not-a-date", "1.00"),
                                         ("2024-02-01", "not-money")])
def test_cli_invalid_add(cli, date, value):
    """Section 2: Invalid dates and amounts fail with stderr and exit 2."""
    result = cli("add", "--date", date, "--amount", value, "--category", "invalid")
    assert result.returncode == 2 and result.stderr.strip()
    assert "invalid" not in success(cli("list"))


def test_summary_totals_order(cli):
    """Section 3: Monthly totals, descending category order, and TOTAL."""
    seeded(cli)
    summary(success(cli("summary", "--month", "2024-02")))


def test_summary_empty_month(cli):
    """Section 3: Empty months, including a missing file, say no expenses."""
    assert "no expenses" in success(cli("summary", "--month", "2024-02"))
    add(cli)
    assert "no expenses" in success(cli("summary", "--month", "2024-03"))


def test_csv_success(cli, tmp_path):
    """Section 4: CSV imports preserve quoted notes and report the count."""
    note = 'Lunch, with "friends"'
    path = tmp_path / "input.csv"
    path.write_text(csv_text([("2024-02-01", "3.45", "food", note),
                              ("2024-02-02", "6.00", "travel", "")]))
    output = success(cli("import-csv", path))
    assert re.search(r"\b2\b", output)
    listing = success(cli("list"))
    assert note in listing and "travel" in listing
    amount(listing, "3.45")


@pytest.mark.parametrize("existing", [False, True])
def test_csv_atomic_failure(cli, tmp_path, existing):
    """Section 4: Every bad row is reported and the import is all-or-nothing."""
    if existing:
        add(cli, category="existing")
    before = success(cli("list"))
    path = tmp_path / "invalid.csv"
    path.write_text(csv_text(bad_rows()))
    result = cli("import-csv", path)
    assert result.returncode == 2
    line_numbers(result.stderr)
    assert success(cli("list")) == before


def test_budget_report(cli, tmp_path):
    """Section 5: Report includes summary, OVER, ok, and no budget categories."""
    seeded(cli)
    add(cli, amount="1.00", category="unbudgeted")
    path = tmp_path / "budgets.json"
    path.write_text('{"food": 10.00, "travel": 20.00}')
    output = success(cli("report", "--month", "2024-02", "--budgets", path))
    assert output.index("travel") < output.index("food") < output.index("unbudgeted") < output.index("TOTAL")
    amount(output, "33.50")
    for category, status in [("food", "OVER"), ("travel", "ok"),
                             ("unbudgeted", "no budget")]:
        assert category in output and status in output, output
    amount(output, "10.00")
    amount(output, "12.50")
    amount(output, "20.00")


def test_budget_under_limit(cli, tmp_path):
    """Section 5: Spending below a category budget is ok."""
    add(cli)
    path = tmp_path / "budgets.json"
    path.write_text('{"food": 50.00}')
    output = success(cli("report", "--month", "2024-02", "--budgets", path))
    assert "food" in output and "ok" in output
    amount(output, "50.00")
    amount(output, "12.34")


def test_web_empty_home(web):
    """Section 6: Empty home succeeds and links to every other page."""
    result = web()
    assert result["status"] == 200
    page = Page(result["body"])
    links = {attrs.get("href") for tag, attrs in page.tags if tag == "a"}
    assert {"/add", "/summary", "/import"} <= links
    amount(page.visible, "0.00")


def test_web_add_and_escape(web):
    """Section 6: Successful add redirects and home escapes user text."""
    note = '<b>Lunch</b>, "friends" & tea'
    result = web("/add", dict(date="2024-02-01", amount="12.34",
                              category="food", note=note))
    assert result["status"] == 303
    assert {k.lower(): v for k, v in result["headers"].items()}["location"] == "/"
    second = web("/add", dict(date="2024-02-02", amount="2.00",
                               category="travel", note=""))
    assert second["status"] == 303
    home = web()
    assert home["status"] == 200
    page = Page(home["body"])
    assert any("2024-02-01" in row and "food" in row and note in row
               for row in page.rows)
    amount(page.visible, "12.34")
    amount(page.visible, "14.34")
    assert note in page.visible
    assert "<b>Lunch</b>" not in home["body"]
    assert not any(tag in {"script", "link", "img", "iframe"} for tag, _ in page.tags)


def test_web_unknown_path(web):
    """Section 6: Unknown paths return 404."""
    assert web("/does-not-exist")["status"] == 404


def test_web_add_form(web):
    """Section 6: Add form supplies the four specified fields."""
    result = web("/add")
    assert result["status"] == 200
    page = Page(result["body"])
    assert any(tag == "form" for tag, _ in page.tags)
    assert {"date", "amount", "category", "note"} <= {
        attrs.get("name") for tag, attrs in page.tags
        if tag in {"input", "textarea"}}


@pytest.mark.parametrize("date,value", [("2024-02-30", "1.00"),
                                         ("2024-02-01", "bad-money")])
def test_web_invalid_add(web, date, value):
    """Section 6: Invalid additions return 400, preserve values, and save nothing."""
    result = web("/add", dict(date=date, amount=value, category="rejected", note="keep me"))
    assert result["status"] == 400
    page = Page(result["body"])
    assert any(tag == "form" for tag, _ in page.tags)
    values = " ".join(attrs.get("value", "") for _, attrs in page.tags) + page.visible
    for value in (date, value, "rejected", "keep me"):
        assert value in values
    assert "rejected" not in Page(web()["body"]).visible


def test_web_summary(modules, tmp_path, web_request, cli):
    """Section 6: Summary uses monthly totals and descending category order."""
    seeded(cli)   # before the app is made: the spec doesn't say a running app sees later writes
    app = modules("web").make_app(str(tmp_path / "expenses.json"))
    result = web_request(app, "/summary?month=2024-02")
    assert result["status"] == 200
    summary(Page(result["body"]).visible)


def test_web_empty_summary_and_default_month(web):
    """Section 6: Empty summary says no expenses and defaults to current month."""
    before = dt.date.today().strftime("%Y-%m")
    result = web("/summary")
    after = dt.date.today().strftime("%Y-%m")
    assert result["status"] == 200
    page = Page(result["body"])
    assert "no expenses" in page.visible
    assert any(tag == "input" and attrs.get("type") == "month"
               and attrs.get("value") in {before, after} for tag, attrs in page.tags)
    assert "no expenses" in Page(web("/summary?month=2024-03")["body"]).visible


@pytest.mark.parametrize("month", ["2024-13", "not-a-month"])
def test_web_invalid_month(web, month):
    """Section 6: Invalid summary months produce a message and status 400."""
    result = web("/summary?month=" + month)
    assert result["status"] == 400
    assert Page(result["body"]).visible.strip()


def test_web_import_form(web):
    """Section 6: Import page provides a CSV textarea."""
    result = web("/import")
    assert result["status"] == 200
    assert any(tag == "textarea" and attrs.get("name")
               for tag, attrs in Page(result["body"]).tags)


def import_field(web):
    return next(attrs["name"] for tag, attrs in Page(web("/import")["body"]).tags
                if tag == "textarea" and attrs.get("name"))


def test_web_import_success(web):
    """Section 6: CSV paste imports quoted notes and reports how many."""
    note = 'Meal, with "friends"'
    result = web("/import", {import_field(web): csv_text([
        ("2024-02-01", "3.45", "food", note),
        ("2024-02-02", "6.00", "travel", "")])})
    assert 200 <= result["status"] < 400
    # Follow a redirect if the success message is shown on its destination.
    if 300 <= result["status"]:
        headers = {k.lower(): v for k, v in result["headers"].items()}
        result = web(headers["location"])
    assert re.search(r"\b2\b", Page(result["body"]).visible)
    listing = Page(web()["body"]).visible
    assert note in listing and "travel" in listing
    amount(listing, "3.45")


def test_web_import_atomic_failure(web):
    """Section 6: Bad CSV paste reports every bad line and imports nothing."""
    web("/add", dict(date="2024-01-01", amount="1.00", category="existing", note=""))
    before = Page(web()["body"]).rows
    result = web("/import", {import_field(web): csv_text(bad_rows())})
    assert result["status"] == 400
    line_numbers(Page(result["body"]).visible)
    assert Page(web()["body"]).rows == before


def test_readme_documents_commands_and_pages(target):
    """Section 7: README documents installation-free commands and every web page."""
    path = target / "README.md"
    assert path.is_file()
    text = path.read_text().lower()
    assert re.search(r"python(?:3)?\s+-m\s+expenses", text)
    for command in ("add", "list", "summary", "import-csv", "report", "serve"):
        assert re.search(r"\b" + re.escape(command) + r"\b", text), command
    assert re.search(r"web\s+ui", text)
    for page in ("/add", "/summary", "/import"):
        assert page in text, page
    assert re.search(r"(?<!\w)/(?!\w)|\bhome\b|\bindex\b", text)


def test_package_module_docstrings(target):
    """Section 7: Every Python module under expenses has a docstring."""
    files = sorted((target / "expenses").rglob("*.py"))
    assert files
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert ast.get_docstring(tree), str(path.relative_to(target))


def test_web_budgets_report(budget_web, cli, tmp_path):
    """Section 6: Explicit budgets file supplies monthly OVER, ok, and no budget data."""
    seeded(cli)
    add(cli, amount="1.00", category="unbudgeted")
    path = tmp_path / "custom-budgets.json"
    path.write_text('{"food": 10.00, "travel": 25.00}')
    result = budget_web(path)("/budgets?month=2024-02")
    assert result["status"] == 200
    text = Page(result["body"]).visible
    for category, status in [("food", "OVER"), ("travel", "ok"),
                             ("unbudgeted", "no budget")]:
        assert category in text and status in text, text
    for value in ("10.00", "12.50", "25.00", "20.00", "1.00"):
        amount(text, value)
    assert "other" not in text


def budget_fields(web):
    page = Page(web("/budgets")["body"])
    # The spec names the concepts, but does not prescribe HTML field names.
    fields = [(attrs.get("name"), attrs.get("type", "text"))
              for tag, attrs in page.tags if tag in {"input", "textarea", "select"}
              and attrs.get("name") and attrs.get("type", "text") not in {"month", "hidden", "submit", "button"}]
    category = next((name for name, kind in fields if "category" in name.lower()), None)
    value = next((name for name, kind in fields if "amount" in name.lower()
                  or "budget" in name.lower() or kind == "number"), None)
    if category is None:
        category = next(name for name, _ in fields if name != value)
    if value is None:
        value = next(name for name, _ in fields if name != category)
    return category, value


def test_web_budgets_form_and_default_month(budget_web, tmp_path):
    """Section 6: Budgets page has a setting form and defaults to the current month."""
    web = budget_web(tmp_path / "custom-budgets.json")
    before = dt.date.today().strftime("%Y-%m")
    result = web("/budgets")
    after = dt.date.today().strftime("%Y-%m")
    assert result["status"] == 200
    page = Page(result["body"])
    assert any(tag == "form" for tag, _ in page.tags)
    assert any(tag == "input" and attrs.get("type") == "month"
               and attrs.get("value") in {before, after} for tag, attrs in page.tags)
    category, value = budget_fields(web)
    assert category != value


@pytest.mark.parametrize("month", ["2024-13", "not-a-month"])
def test_web_budgets_invalid_month(budget_web, tmp_path, month):
    """Section 6: Invalid budget-report months give a message and status 400."""
    result = budget_web(tmp_path / "custom-budgets.json")("/budgets?month=" + month)
    assert result["status"] == 400
    assert Page(result["body"]).visible.strip()


@pytest.mark.parametrize("default", [False, True])
def test_web_set_budget(budget_web, cli, tmp_path, monkeypatch, default):
    """Section 6: Setting a budget persists to explicit/default files and redirects."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ("budgets.json" if default else "custom-budgets.json")
    web = budget_web(None if default else path)
    category, value = budget_fields(web)
    result = web("/budgets", {category: "food", value: "50.00"})
    assert result["status"] == 303
    assert {k.lower(): v for k, v in result["headers"].items()}["location"] == "/budgets"
    assert path.is_file()
    # Reopen through the app and CLI to observe persistence through public interfaces.
    add(cli)
    reopened = budget_web(None if default else path)("/budgets?month=2024-02")
    assert reopened["status"] == 200
    text = Page(reopened["body"]).visible
    assert "food" in text and "ok" in text
    amount(text, "50.00")
    amount(text, "12.34")
    report = success(cli("report", "--month", "2024-02", "--budgets", path))
    amount(report, "50.00")


def test_web_budget_bad_amount(budget_web, tmp_path):
    """Section 6: An invalid budget amount gives a message and status 400."""
    web = budget_web(tmp_path / "custom-budgets.json")
    category, value = budget_fields(web)
    result = web("/budgets", {category: "food", value: "not-money"})
    assert result["status"] == 400
    assert Page(result["body"]).visible.strip()


def test_web_home_links_to_budgets(web):
    """Section 6: Home links to the budgets page."""
    result = web()
    assert result["status"] == 200
    assert any(tag == "a" and attrs.get("href") == "/budgets"
               for tag, attrs in Page(result["body"]).tags)
