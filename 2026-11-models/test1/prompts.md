# Test 1 prompts

Each run is a fresh git repository holding `problem.md` and SpecKit's templates and skills. The
agent gets one prompt a step, in this order: the step's section below, then "Every step". The
runner (`test1.sh`) reads this file.

## specify

Read the file .claude/skills/speckit-specify/SKILL.md in this repository (an instruction file, not one of Hermes's skills) and follow it. The input is the problem statement in problem.md. Write the spec to spec.md in the feature folder the skill's script creates under specs/ (it records that folder in .specify/feature.json).

## plan

Read the file .claude/skills/speckit-plan/SKILL.md in this repository (an instruction file, not one of Hermes's skills) and follow it. Write it to plan.md in the feature folder under specs/ named in .specify/feature.json, beside spec.md.

## tasks

Read the file .claude/skills/speckit-tasks/SKILL.md in this repository (an instruction file, not one of Hermes's skills) and follow it. Write it to tasks.md in the feature folder under specs/ named in .specify/feature.json, beside spec.md.

## estimate

From the spec, plan and tasks in this repository, estimate the effort to build the solution, separately for the desktop app and the mobile app: in hours of a human developer's work, and in the tokens an AI coding agent would use. Write estimate.md with a section "## Desktop" and a section "## Mobile". Each section holds a line "Human hours: <number>" and a line "Tokens: <number>", followed by how you reached them.

## Every step

Where this step needs a decision that problem.md doesn't settle, don't stop and don't decide silently: choose what a careful developer would, and add the question and the answer you assumed to questions.md at the repository root, for the owner to confirm. Create questions.md if it isn't there, even if you have no question. Finish the step by committing your work with git.

No one is available to answer questions: run the step non-interactively.
