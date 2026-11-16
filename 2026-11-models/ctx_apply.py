"""On Sherlock, from the gate (sherlock.sh): sets one model's context, as the gate measured it, in
~/.hermes/config.yaml: its entry in custom_providers for the lane's server, and model.context_length
when it is the configured default model (Hermes counts that one only for the default). Subagents stay
on (delegation, one at a time: the server answers one request at a time). The first run keeps the
config as it was in config.yaml.before-ctx. The gate then reads the context back through Hermes's own
resolver (test0/hermes_ctx.py), so a setting Hermes ignores stops the round.
Usage: python3 ctx_apply.py <model> <context> <server url>"""
import re
import shutil
import sys
from pathlib import Path

MODEL, CTX, URL = sys.argv[1], int(sys.argv[2]), sys.argv[3]
CFG = Path.home() / ".hermes" / "config.yaml"
s = CFG.read_text()
keep = CFG.with_name("config.yaml.before-ctx")
if not keep.exists():
    shutil.copy(CFG, keep)
s = re.sub(r"(?m)^  cli: \[clarify, code_execution, file,", "  cli: [clarify, code_execution, delegation, file,", s)
if not re.search(r"(?m)^  max_concurrent_children: 1\b", s):
    s = re.sub(r"(?m)^delegation:\n", "delegation:\n  max_concurrent_children: 1   # the model server answers one request at a time\n", s, count=1)
default = re.search(r'(?m)^  default: "?([^"\n]+)"?', s)
if default and default.group(1).strip() == MODEL:
    s = re.sub(r"(?m)^  context_length: \d+\n(  max_tokens:)", f"  context_length: {CTX}\n\\1", s, count=1)

# This script's own block, last in the file: one provider per server, each with its models' contexts
block = re.search(r"(?ms)^custom_providers:.*\Z", s)
providers = {}   # url -> {model: context}
if block:
    for url, body in re.findall(r"(?ms)^    base_url: (\S+)\n    models:\n((?:      .*\n?)*)", block.group(0)):
        providers[url] = dict(re.findall(r"(?m)^      (\S+):\n        context_length: (\d+)", body))
    s = s[:block.start()]
providers.setdefault(URL, {})[MODEL] = str(CTX)
out = "custom_providers:   # each model's context, measured by the gate (tests/2026-11-models, sherlock.sh)\n"
for url, models in providers.items():
    out += f"  - name: {'adlerbot' if '192.168.40.110' in url else url.split('//')[1].split(':')[0]}\n    base_url: {url}\n    models:\n"
    out += "".join(f"      {m}:\n        context_length: {n}\n" for m, n in models.items())
CFG.write_text(s.rstrip("\n") + "\n" + out)
