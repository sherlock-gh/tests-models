# Test 1: tasks

Each task is a fresh repo on Sherlock holding `speckit/` (SpecKit's own files, copied unchanged, not installed) and the task's `brief.md`. Each milestone is one Hermes job with the prompt below, and it ends in a commit.

## App plans: `expense-tracker`, `habitkit`

1. Read the file `.claude/skills/speckit-specify/SKILL.md` … and follow it. The input is the brief in `brief.md`.
2. Read the file `.claude/skills/speckit-plan/SKILL.md` … and follow it.
3. Read the file `.claude/skills/speckit-tasks/SKILL.md` … and follow it.

Every prompt ends: "No one is available to answer questions: run the step non-interactively." and "Commit when the step is done." ("…" stands for the first step's wording. Round 2's prompts said "Follow `<path>`", which sent two models to Hermes's skill lookup instead; changed for round 3.) The prompts are written in `../test1.sh`; the check after each step is `check.py`.
