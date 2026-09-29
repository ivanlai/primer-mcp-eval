# primer-mcp-eval

Does [primer-mcp](https://github.com/ivanlai/primer-mcp) change how AI coding agents work?

## Purpose

primer-mcp is an MCP server for planning-first development. It gives a coding agent ticket tools (epics, decision records, stories, tasks) and a short CLAUDE.md section that asks it to plan before coding, record decisions, and complete then verify its work. The claim is that an agent with primer-mcp works differently: it plans before it edits, leaves a written record of what it decided and did, verifies before finishing, and stays within scope.

This repo tests that claim. It gives Claude Code the same coding requests with and without primer-mcp and compares what the agent does. It is deliberately small, a credible measurement of one question rather than a benchmark framework.

## Methodology

The design is recorded as decision records in [`primer/adrs/`](primer/adrs/). This eval is planned and tracked with primer-mcp itself.

**The test app** ([`fixtures/app/`](fixtures/app/), ADR-001). A small command-line expense tracker in Python, about 600 lines including tests, written for this eval so that no agent has seen it before. You record expenses (`expenses add 12.50 groceries --date 2026-03-01`), list them with month and category filters, list the categories in use, and print a monthly summary: the total, the daily average, and a per-category breakdown with each category's share. Amounts are stored as whole pence in a JSON file. It has a passing pytest suite and three deliberately planted bugs that the suite doesn't catch.

**Scenarios** ([`scenarios/`](scenarios/), ADR-001). Twelve change requests, each written the way a user would ask:

| Kind | # | Examples |
|---|---|---|
| Feature | 4 | edit and delete expenses; monthly budgets; CSV export and import; recurring expenses |
| Bug fix | 3 | "a 0.29 stamp shows as 0.28"; the March summary includes last year's March; the category filter is case-sensitive |
| Refactor | 2 | move the summary text into a `render_summary` function; move JSON conversion out of the `Expense` record |
| Trivial | 2 | rename a label; show a count per category |
| Ambiguous | 1 | "Make `expenses summary` more useful." |

Prompts never mention primer-mcp, tickets or planning, and both arms get identical prompts. Each prompt ends with one line saying no one is available to answer questions. Each scenario has a functional check, which asserts only what the prompt asks for, and a reference solution that proves the check can be passed. `scripts/validate_scenarios.py` confirms mechanically that every check fails on the app as shipped and passes with its reference.

**Two arms** (ADR-003):
- *Baseline:* plain Claude Code with no MCP servers and no CLAUDE.md.
- *Primer:* the same, plus primer-mcp at a pinned version, with `init_project` already run (the `primer/` folder and its CLAUDE.md section are in place).

**Harness** (ADR-002). Every run is a separate headless Claude Code session (`claude -p`) at a pinned CLI version, model and primer-mcp version (`eval.toml`). Each run starts from a fresh git repo of the app, in a temporary folder outside this repo, with an empty `HOME`. No user-level instructions, memory, skills, hooks or MCP servers can reach it. An isolation check reads each session's start-up event and fails any run that loaded something it shouldn't, or that looked outside its own repo.

**Metrics** (ADR-004). All are computed automatically from the saved transcript and final repo, with no model in the scoring loop (`scripts/score.py`):

| Metric | Rule |
|---|---|
| Planned before first code edit | a planning tool, the Plan agent, a primer-mcp tool or a Markdown write came before the first source edit |
| Durable record | a Markdown file (ticket, decision, plan, notes) was added or changed in the repo |
| Verified before finishing | tests were run after the last source edit |
| Stayed in scope | number of changed files outside the scenario's expected files |
| Functional pass | the scenario's check passes on the final repo |
| Cost | turns, time, and estimated cost |

primer-mcp-specific numbers (tickets created, `complete_task` and `verify_task` used) are reported for the primer arm only, because the baseline would score zero on them by construction.

**Runs** (ADR-005). A 24-run pilot (every scenario once per arm) tests the pipeline and the scoring rules against hand-read transcripts. The headline is then 3 runs per scenario per arm (72 runs), with confidence intervals bootstrapped over scenarios, since runs of the same scenario are not independent.

**Limits, stated up front.** The results describe Claude Code on one small, clean codebase. The planning metrics measure whether planning happened and was written down, not how good it was. Planning written only in chat text is not counted. Three runs per scenario can show large differences, not subtle ones.

## Results

**Headline** (72 runs: 12 scenarios × 2 arms × 3 repetitions, all at Claude Code 2.1.283, `claude-sonnet-5`, primer-mcp 0.1.7; every run passed the isolation check). Full tables: [`results/headline/summary.md`](results/headline/summary.md); per-run rows: [`results/headline/runs.csv`](results/headline/runs.csv).

| Metric | Baseline | primer-mcp |
|---|---|---|
| Planned before first code edit | 0% (0–0) | 53% (25–78) |
| Left a durable record | 0% (0–0) | 53% (25–78) |
| Verified before finishing | 100% | 100% |
| Functional pass | 89% (75–100) | 97% (92–100) |
| Repo's own tests pass | 100% | 100% |
| Stopped to ask | 0% | 0% |
| Out-of-scope files (mean) | 0 | 0 |
| Mean turns / time / est. cost | 19 / 66s / $0.29 | 30 / 101s / $0.44 |

95% intervals in brackets, bootstrapped over scenarios. Cost is Claude Code's own API-equivalent estimate; the runs used a subscription, and the whole batch came to an estimated $26.

**By kind of change** (3 runs per scenario per arm):

| Kind | Planned first (baseline → primer) | Functional (baseline → primer) | Mean est. cost (baseline → primer) |
|---|---|---|---|
| Feature (4) | 0/12 → 12/12 | 9/12 → 11/12 | $0.45 → $0.72 |
| Ambiguous (1) | 0/3 → 3/3 | 2/3 → 3/3 | $0.40 → $0.74 |
| Bug fix (3) | 0/9 → 1/9 | 9/9 → 9/9 | $0.16 → $0.20 |
| Refactor (2) | 0/6 → 0/6 | 6/6 → 6/6 | $0.22 → $0.23 |
| Trivial (2) | 0/6 → 3/6 | 6/6 → 6/6 | $0.15 → $0.29 |

**What the runs show.**
- On every feature and ambiguous run, the primer-mcp agent created tickets before editing code and left them in the repo; the baseline never wrote a plan down. On bug fixes and refactors the two arms behaved almost identically, in both behaviour and cost.
- In the one trivial scenario where it planned ("show a count per category"), each run set up the generic epic and standing small-fixes story that later small changes would go under ("Bug fixes & small improvements" and similar), then one task. Every run starts from an empty `primer/` folder, so every run paid this one-off setup, which more than doubled the cost of that scenario. In ongoing use it is paid once. The other trivial scenario (renaming a label) never used the tools.
- Of the 36 primer-arm runs, 21 called primer-mcp at all, averaging 2.25 tickets each, and 18 used both `complete_task` and `verify_task`.
- Functional failures, hand-checked: two baseline and one primer run on budgets left out the budget amount the prompt asked for; one baseline CSV import reported only the first bad line, not each one. The fourth baseline failure (ambiguous request) is a false negative in the check: the agent added a month-over-month line and fixed a real bug, but the check's data has only one month, so the default output looked unchanged. Scored as in the pre-set rules, but it means the functional gap is 2–3 runs, well inside the intervals.
- The pilot's one stall (the agent stopped to ask for ticket approval despite being told no one would answer) did not recur in 36 primer runs.

**Pilot** (24 runs, used to test the pipeline and scoring; not part of the headline): [`results/pilot/summary.md`](results/pilot/summary.md). It showed the same pattern.

## Verdict

primer-mcp changes how the agent works on the kind of work it is aimed at. On features and open-ended requests, adding it took planning-before-coding and a written record from never to every time, in 15 of 15 runs against 0 of 15. On bug fixes and refactors it made almost no difference. That makes the overall 53% an average of "always" and "rarely", not a coin flip.

It did not measurably change outcomes. Both arms verified every time, stayed in scope and kept the repo's tests passing. primer-mcp had slightly more functional passes, but the difference is within noise at this size.

The cost is about 50% more turns, time and estimated spend overall, concentrated where it plans (+60% on features), plus a one-off cost to set up the standing structure for small fixes, which this design charges on every run.

**Limits.** One model, one CLI version, one small clean codebase written for the eval. Three repetitions per scenario. The planning metrics show that planning happened and was written down, not that it was good. The functional checks are narrow; one false negative is noted above. Every run was told no one would answer questions, so this says nothing about how primer-mcp's nudges to propose tickets play out with a user present, who can decline them. Every run also started from an empty `primer/` folder, so the results don't show how the agent handles small fixes once a standing structure exists.

## Reproducing

```
python3 scripts/validate_scenarios.py                       # scenarios are well formed
python3 scripts/run_eval.py --batch pilot --dry-run         # what each run would do
python3 scripts/run_eval.py --batch headline --reps 3       # real runs (see scripts/README.md for auth)
python3 scripts/score.py --batch headline                   # results/headline/summary.md
uv run --with pytest --no-project pytest tests              # offline tests of the scripts
```
