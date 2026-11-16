"""The context Hermes will give a test job's model, by Hermes's own resolver, as the job runs it
(hermes-in --provider custom -m <model>, CUSTOM_BASE_URL=<server url>): model.context_length counts
only for the configured default model, then custom_providers, then Hermes's cache and probes.
Run with Hermes's own Python (lib.sh, hermes_ctx). Usage: hermes_ctx.py <model> <server url>   Prints the context."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
os.environ.setdefault("HERMES_HOME", os.path.expanduser("~/.hermes"))
import hermes_bootstrap  # noqa: E402,F401  (Hermes's own package path)

from agent.model_metadata import get_model_context_length
from hermes_cli.config import get_compatible_custom_providers, load_config

model, url = sys.argv[1], sys.argv[2]
cfg = load_config()
m = cfg.get("model") or {}
pin = m.get("context_length") if str(m.get("default") or "").strip() == model else None
print(get_model_context_length(model, base_url=url, provider="custom",
                               custom_providers=get_compatible_custom_providers(cfg), config_context_length=pin))
