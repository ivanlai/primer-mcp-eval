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

*Pending.* The pilot is running. Headline results will be published here, with the per-arm rates, intervals, per-scenario differences and cost, once the 72 headline runs are complete.

## Verdict

*Pending the headline runs.*

## Reproducing

```
python3 scripts/validate_scenarios.py                       # scenarios are well formed
python3 scripts/run_eval.py --batch pilot --dry-run         # what each run would do
python3 scripts/run_eval.py --batch headline --reps 3       # real runs (see scripts/README.md for auth)
python3 scripts/score.py --batch headline                   # results/headline/summary.md
uv run --with pytest --no-project pytest tests              # offline tests of the scripts
```
