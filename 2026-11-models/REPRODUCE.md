# Reproducing this test

These files are enough to recreate the test with your own agent, models and scripts:

| File | What it gives you |
| --- | --- |
| `README.md` | What the test answers, what "best" means, the order of the tests, the conditions and how runs are judged |
| `test1/problem.md` | The problem every model plans from |
| `test1/prompts.md` | The prompt for each step of test 1 |
| `hosts/sherlock/hermes/SOUL.md` | The agent's standing instructions, loaded in every session |

## Setup used here

- **Agent:** Hermes Agent v0.21.5, with that `SOUL.md` as its standing instructions. Settings:
  64K context, 8192 output tokens a turn, at most 150 turns, the tools for files, the terminal,
  code execution, memory, skills, to-dos and the web, and the loop guard's hard stop on.
- **Models:** the local models named in `README.md`, 4-bit MLX builds (Qwen3.8-27B also 8-bit)
  served by MLX-LM 0.32 through an OpenAI-compatible API, or by Ollama where MLX-LM can't run
  the model. Thinking is off, and each model uses its publisher's sampling.
- **Hosts:** a MacBook Pro M3 Max with 128 GB, and an M1 Max with 64 GB for models that leave it
  16 GB free. The agent runs on a third machine.
- **SpecKit:** each run's repository holds SpecKit's specify, plan and tasks skills and its
  templates (github.com/github/spec-kit), with `problem.md`.

## Running it

For each model, three runs of test 1. Each run is a fresh repository, with the four steps of
`prompts.md` in order, and a run ends at the first step that fails. A step passes when its
document has every section its template requires, filled in with no placeholders, and is
committed. Then grade the finished plans blind, as `README.md` says.
