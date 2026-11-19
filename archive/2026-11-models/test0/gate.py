"""Test 0's calls (from Sherlock, the path Hermes uses): one reply, then 20 prompts that each need a tool call.
A call parses when the reply holds a tool call to one of the offered tools, with arguments
that are a JSON object carrying that tool's required fields. 3 minutes a call.
Usage: python3 gate.py <model> <server url>   Prints: replied<TAB>parsed (of 20)<TAB>tokens/s
Each call's outcome goes to stderr (results' test0-calls.log)."""
import json
import sys
import time
import urllib.error
import urllib.request

MODEL, URL = sys.argv[1], sys.argv[2] + "/chat/completions"   # the lane's server (31 Oct: a fixed
# address sent every second server's gate to Adlerbot)


def tool(name, desc, **params):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "required": list(params),
                       "properties": {k: {"type": "string", "description": v} for k, v in params.items()}}}}


TOOLS = [
    tool("read_file", "Read a text file in the repository.", path="Path relative to the repo root"),
    tool("write_file", "Create or overwrite a text file.", path="Path relative to the repo root",
         content="The whole new content of the file"),
    tool("run_command", "Run a shell command in the repo root and return its output.",
         command="The command line"),
    tool("search_files", "Search the repository's files for a regular expression.",
         pattern="The regular expression"),
    tool("list_dir", "List a directory of the repository.", path="Directory, relative to the repo root"),
]
REQUIRED = {t["function"]["name"]: t["function"]["parameters"]["required"] for t in TOOLS}

PROMPTS = [
    "What does README.md say? Read it.",
    "Create notes/todo.md with a heading 'To do' and one item: 'write the tests'.",
    "Run the test suite with python3 -m pytest -q.",
    "Find every place the word TODO appears in the code.",
    "What files are in the src folder?",
    "Show me the contents of pyproject.toml.",
    "Commit everything with the message 'first draft'.",
    "Write a .gitignore that ignores __pycache__/ and *.json.",
    "Which files import the json module? Search for it.",
    "List the top level of the repository.",
    "Check which Python version is installed.",
    "Open src/app.py so we can look at the main function.",
    "Create a file hello.py that prints 'Hello, world!' when run.",
    "Search for functions named main in the repository.",
    "Run git status to see what changed.",
    "Look inside the tests directory.",
    "Read the file docs/setup.md.",
    "Replace CHANGELOG.md with a single line: '0.1.0: first release'.",
    "Count the lines of every Python file with wc -l.",
    "Find where the class Expense is defined.",
]
SYSTEM = "You are a coding agent working in a repository. Use the tools to act; do not just describe."


def post(body, limit=180):
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=limit) as r:
        return json.load(r)


def parses(reply):
    calls = (reply["choices"][0]["message"].get("tool_calls") or [])
    if not calls:
        text = (reply["choices"][0]["message"].get("content") or "").strip()
        print(f"  no tool call; the reply: {text[:160]!r}", file=sys.stderr)
        return False
    fn = calls[0].get("function", {})
    args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return False
    ok = fn.get("name") in REQUIRED and isinstance(args, dict) and all(k in args for k in REQUIRED[fn["name"]])
    if not ok:
        print(f"  a call that doesn't fit the tools: {json.dumps(fn)[:200]}", file=sys.stderr)
    return ok


def transport(e):   # the connection failed or the server erred (5xx): the machine, not the model.
    # A call that times out stays the model's: 3 min a call is the gate's rule.
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500
    return isinstance(e, (ConnectionError, urllib.error.URLError)) and not isinstance(getattr(e, "reason", e), TimeoutError)


def main():
    replied, speed, broken = "no", 0.0, []
    try:
        t = time.time()
        r = post({"model": MODEL, "max_tokens": 200,
                  "messages": [{"role": "user", "content": "Write three sentences about the sea."}]})
        if (r["choices"][0]["message"].get("content") or "").strip():
            replied = "yes"
            speed = r.get("usage", {}).get("completion_tokens", 0) / (time.time() - t)
    except Exception as e:  # noqa: BLE001 - any failure is "no reply", recorded
        print(f"reply failed: {e}", file=sys.stderr)
        if transport(e):
            broken.append(e)
    parsed = 0
    print(f"gate {MODEL} at {URL}: replied {replied}, {speed:.1f} tok/s", file=sys.stderr)
    for p in PROMPTS:
        print(f"call: {p[:50]}", file=sys.stderr)
        try:
            parsed += parses(post({"model": MODEL, "max_tokens": 1024, "tools": TOOLS,
                                   "messages": [{"role": "system", "content": SYSTEM},
                                                {"role": "user", "content": p}]}))
        except Exception as e:  # noqa: BLE001 - a call that errors or times out doesn't parse
            print(f"call failed: {p[:40]}: {e}", file=sys.stderr)
            if transport(e):
                broken.append(e)
    print(f"{replied}\t{parsed}\t{speed:.1f}")
    if broken:   # exit 2: the runner stops the round rather than record a result
        print(f"connection failures: {len(broken)}, first: {broken[0]}", file=sys.stderr)
        sys.exit(2)


main()
