# Questions for the owner

Decision records for this step (estimating build effort). Each entry states the
question problem.md does not settle and the answer assumed, as a careful developer
would. The estimates in estimate.md depend on these; if an answer is wrong, the
affected number changes as noted.

## Q10. Who builds it — one full-stack developer or a Python + Swift pair?

Problem.md gives two apps but no team. If one full-stack developer builds both
tracks solo, the total is 70 + 40 = 110 human hours. If a Python developer and an
iOS/Swift developer work in parallel, wall-clock time halves but the total paid
hours stay ~110 (plus a little coordination). ASSUMED: estimates are per-track
hours for one competent developer per track, as presented in estimate.md
(desktop 70, mobile 40). Hours here are focused work hours, not elapsed days.

## Q11. What counts as "the tokens an AI coding agent would use"?

Tokens could mean output tokens only, input+output of model calls only, or all
tokens including embeddings/RAG. ASSUMED: total tokens across all model calls
(prompt/input + completion/output) for one competent agent run that takes the
track from the tasks in tasks.md to green test suites — the number a provider bill
or budget would resemble. Sub-agent delegation, if the agent uses it, is included.

## Q12. Productivity baseline for the human-hour figures?

"Hours of a human developer's work" depends on who the developer is. ASSUMED: a
competent developer who already knows Python 3.14 + stdlib http.server and Swift
6.1 + Foundation, working on a machine with the toolchains installed, with all
spec artifacts (spec, plan, data-model, contracts, golden vectors, quickstart)
already written as they are in this repo. A junior developer or one missing the
timezone/Decimal subtleties would land nearer 1.5–2× these numbers.

## Q13. Does the estimate include authoring the spec, plan and tasks?

This repo already contains them (they were produced by a prior step). ASSUMED: no —
estimate.md covers only building the two apps (implementing tasks T001–T054, code +
tests + validation). For scale, authoring the spec suite cost this agent roughly
200,000–250,000 extra tokens and would be a day or two of a senior developer; add
it if the owner budgets from an empty repo.

## Q14. Are the two tracks estimated independently (double-counting shared design)?

The mobile track is a structural mirror of the desktop track (research R5), and its
40 h assumes the booking rule, cascade semantics and golden-vector debugging were
already paid for on the desktop side. ASSUMED: estimate both tracks as if built in
desktop-first order, so mobile benefits from desktop's finished design. An
owner budgeting mobile alone (desktop never built, or built later) should use
roughly desktop's hours plus Swift translation cost — nearer 60–75 h — not 40 h.
