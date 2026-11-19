# tests-models

The owner's model tests for his home lab: which local and cloud models, with which settings, do each kind of work best. The guardrails are in the user-level CLAUDE.md. Here, the goal is the owner getting a local agent system that runs on its own and that he can trust; the subjects are briefs, models (local, Claude, Codex) and hosts. Each test's README says what it answers and how. The October and November tests are in `archive/`, stopped; their rules are `archive/CLAUDE.md`.

## Roles

- **Hermes** on Sherlock does the tests' work. **Adlerbot** (192.168.40.110) is the only model host: models are switched through inferctl (:8090) and nothing else; nobody logs into it.
- **You** (Claude on Sherlock) set tests up, run them and analyse results. You don't do the work the test measures.
- Results stay on Sherlock under `<test>/results/` (not committed); numbers and grades go into the repo, one set a run. Workspaces and usage files are disposable once nothing needs them.

## Working with the owner

- Short: state first, then the command, the machine and the account. Explain only when asked or when a decision is his. Name whose password, on which machine, at every prompt.
- When a rule in this repo conflicts with what he asks, say so in the same reply and change it.
- Commit and push every change as it's made (Sherlock's git workflow).
- Hosts' setup (Hermes's config, inferctl, Modelfiles) is recorded in AI-Infra on Dr Watson; a change to a host's setup is the owner's to back up (`bin/backup`).
