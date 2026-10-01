# primer-mcp-eval

Does [primer-mcp](https://github.com/ivanlai/primer-mcp) change how AI coding agents work?

**At a glance.**
- **Question:** does primer-mcp, a planning-first MCP server, change how an AI coding agent works?
- **Design:** 12 change requests on an app written for the eval, given to headless Claude Code three ways (plain, with a one-line planning instruction in CLAUDE.md, and with primer-mcp), 3 times each: 108 isolated runs at pinned versions, scored deterministically from transcripts with no LLM judge.
- **Result:** on features and open-ended requests, primer-mcp took a written plan before coding from 0 of 15 runs to 15 of 15, at about 50% more cost. One line in CLAUDE.md ("Plan first, and save the plan in docs/ before changing code.") got a written plan in all 36 runs, on every kind of change, for about 7% more. Outcomes (functional checks, tests, scope) showed no measurable difference between the three.
- **What primer-mcp adds** over that line is the shape of the record: intent kept apart from implementation, decisions with their rejected alternatives, and a status kept up to date. The plan files had none of these.
- **Open question:** whether that structure pays off in later sessions, which this single-session design cannot show.

## Purpose

primer-mcp is an MCP server for planning-first development. It gives a coding agent ticket tools (epics, decision records, stories, tasks) and a short CLAUDE.md section that asks it to plan before coding, record decisions, and complete then verify its work. The claim is that an agent with primer-mcp works differently: it plans before it edits, leaves a written record of what it decided and did, verifies before finishing, and stays within scope.

This repo tests that claim. It gives Claude Code the same coding requests with and without primer-mcp, and with a one-line planning instruction instead, and compares what the agent does. It is deliberately small, a credible measurement of one question rather than a benchmark framework.

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

Prompts never mention primer-mcp, tickets or planning, and every arm gets identical prompts. Each prompt ends with one line saying no one is available to answer questions. Each scenario has a functional check, which asserts only what the prompt asks for, and a reference solution that proves the check can be passed. `scripts/validate_scenarios.py` confirms mechanically that every check fails on the app as shipped and passes with its reference.

**Three arms** (ADR-003, ADR-007):
- *Baseline:* plain Claude Code with no MCP servers and no CLAUDE.md.
- *Instructions:* the baseline plus a CLAUDE.md containing only "Plan first, and save the plan in docs/ before changing code." It tests the obvious objection: couldn't one line of instructions do what primer-mcp does?
- *Primer:* the baseline plus primer-mcp at a pinned version, with `init_project` already run (the `primer/` folder and its CLAUDE.md section are in place).

**Harness** (ADR-002). Every run is a separate headless Claude Code session (`claude -p`) at a pinned CLI version, model and primer-mcp version (`eval.toml`). Each run starts from a fresh git repo of the app, in a temporary folder outside this repo, with an empty `HOME`. No user-level instructions, memory, skills, hooks or MCP servers can reach it. An isolation check reads each session's start-up event and fails any run that loaded something it shouldn't, or that looked outside its own repo.

**Metrics** (ADR-004). All are computed automatically from the saved transcript and final repo, with no model in the scoring loop (`scripts/score.py`):

| Metric | Rule |
|---|---|
| Wrote a plan before first code edit | a planning tool, the Plan agent, a primer-mcp tool that creates a ticket, or a Markdown write came before the first source edit |
| Durable record | a Markdown file (ticket, decision, plan, notes) was added or changed in the repo |
| Verified before finishing | tests were run after the last source edit |
| Stayed in scope | number of changed files outside the scenario's expected files |
| Functional pass | the scenario's check passes on the final repo |
| Cost | turns, time, and estimated cost |

primer-mcp-specific numbers (tickets created, `complete_task` and `verify_task` used) are reported for the primer arm only, because the other arms would score zero on them by construction.

**Runs** (ADR-005). A 24-run pilot (every scenario once per arm) tests the pipeline and the scoring rules against transcripts inspected with Claude Code. The headline is then 3 runs per scenario per arm (108 runs), with 95% intervals that treat the 12 scenarios, not the individual runs, as the sample (see Statistics under Engineering notes).

**Limits, stated up front.** The results describe Claude Code on one small, clean codebase. The planning metrics measure whether planning happened and was written down, not how good it was. Planning written only in chat text is not counted. Three runs per scenario can show large differences, not subtle ones.

## Results

**Headline** (108 runs: 12 scenarios × 3 arms × 3 repetitions, all at Claude Code 2.1.283, `claude-sonnet-5`, primer-mcp 0.1.7; every run passed the isolation check). Full tables: [`results/headline/summary.md`](results/headline/summary.md); per-run rows: [`results/headline/runs.csv`](results/headline/runs.csv).

| Metric | Baseline | Instructions | primer-mcp |
|---|---|---|---|
| Wrote a plan before first code edit | 0% (0–0) | 100% (100–100) | 53% (25–78) |
| Left a durable record | 0% (0–0) | 100% (100–100) | 53% (25–78) |
| Verified before finishing | 100% | 100% | 100% |
| Functional pass | 89% (75–100) | 92% (75–100) | 97% (92–100) |
| Repo's own tests pass | 100% | 100% | 100% |
| Stopped to ask | 0% | 0% | 0% |
| Out-of-scope files (mean) | 0 | 0 | 0 |
| Mean turns / time / est. cost | 19 / 66s / $0.29 | 20 / 81s / $0.31 | 30 / 101s / $0.44 |

The two planning metrics coincide because every plan was a file left in the repo: a ticket in the primer arm, a `docs/` file in the instructions arm. 95% intervals in brackets (how much each rate could vary by chance; see Statistics under Engineering notes). Cost is Claude Code's own API-equivalent estimate; the runs used a subscription, and the whole batch came to an estimated $37.

**By kind of change** (3 runs per scenario per arm; baseline · instructions · primer-mcp):

| Kind | Wrote a plan before first code edit | Functional | Mean est. cost |
|---|---|---|---|
| Feature (4) | 0/12 · 12/12 · 12/12 | 9/12 · 9/12 · 11/12 | $0.45 · $0.46 · $0.72 |
| Ambiguous (1) | 0/3 · 3/3 · 3/3 | 2/3 · 3/3 · 3/3 | $0.40 · $0.40 · $0.74 |
| Bug fix (3) | 0/9 · 9/9 · 1/9 | 9/9 · 9/9 · 9/9 | $0.16 · $0.21 · $0.20 |
| Refactor (2) | 0/6 · 6/6 · 0/6 | 6/6 · 6/6 · 6/6 | $0.22 · $0.24 · $0.23 |
| Trivial (2) | 0/6 · 6/6 · 3/6 | 6/6 · 6/6 · 6/6 | $0.15 · $0.18 · $0.29 |

**What the runs show.**
- On every feature and ambiguous run, the primer-mcp agent created tickets before editing code and left them in the repo; the baseline never wrote a plan down. On bug fixes and refactors primer-mcp behaved much like the baseline.
- The instructions arm followed its one line every time: each run wrote one plan file in `docs/` before its first code edit, including on the bug fixes, refactors and trivial changes where primer-mcp mostly didn't plan. That cost a few turns, not the 15–25 that tickets took.
- The plan files were mostly implementation steps, down to individual expressions, under a short goal. A keyword search of all 36, checked by reading, found none that recorded a rejected alternative, acceptance criteria or a status; none was updated once coding started; and each run chose its own file name and layout (`docs/fix-amount-rounding.md`, `docs/0001-fix-amount-parsing-float-truncation.md`, `docs/monthly-budgets-plan.md`). primer-mcp's tickets have slots for these by construction, though how well they're filled isn't scored, and the primer runs wrote only 4 ADRs in all.
- In the one trivial scenario where it planned ("show a count per category"), each run set up the generic epic and standing bug-fix story that later small changes would go under ("Bug fixes & small improvements" and similar), then one task. Every run starts from an empty `primer/` folder, so every run paid this one-off setup, which more than doubled the cost of that scenario. In ongoing use it is paid once. The other trivial scenario (renaming a label) never used the tools.
- Of the 36 primer-arm runs, 21 called primer-mcp at least once. 19 created tickets (81 in all, about 4 per run), and 18 of those used both `complete_task` and `verify_task`. The other 2, both on the same bug fix, only listed the (empty) tickets and then fixed the bug without creating any.
- Functional failures (8 in all, each inspected with Claude Code):
  - *Budgets* (2 baseline, 3 instructions, 1 primer): the summary didn't show the budget amount, which the prompt asked for. In the instructions arm all three plans specified the over-budget line without the amount, so the plan carried the mistake into the code.
  - *CSV import* (1 baseline): the error reported only the first bad line, not each one.
  - *Ambiguous request* (1 baseline): a flaw in the check, not the agent. The agent added a month-over-month comparison and fixed a real bug, but the check's data covers only one month, so the new line never appeared. It stays scored as a failure under the pre-set rules.

  While primer-mcp looks like a slight improvement, the gap (2 or 3 runs, depending on how the ambiguous case is counted) is too small to rule out statistical noise with a sample this size.
- The pilot's one stall (the agent stopped to ask for ticket approval despite being told no one would answer) did not recur in 36 primer runs.

**Pilot** (24 runs, used to test the pipeline and scoring; not part of the headline): [`results/pilot/summary.md`](results/pilot/summary.md). It showed the same pattern.

## Verdict

primer-mcp changes how the agent works on larger pieces of work. On features and open-ended requests, adding it took planning-before-coding and a written record from never to every time, in 15 of 15 runs against 0 of 15. On bug fixes and refactors it made almost no difference, though that may change once a standing bug-fix story exists.

But primer-mcp isn't needed to get a written plan. One line in CLAUDE.md asking for a saved plan got one in every run, on every kind of change, at a fraction of the cost. What primer-mcp adds over that line is the shape of the record: intent kept apart from implementation in fixed slots, decisions with their rejected alternatives, and a status that moves as work is completed and verified. The plan files had none of these. This eval measures whether a record exists, not whether its shape helps, so whether primer-mcp's structure pays for its cost over a plan file in later sessions is the open question (see Limits).

None of the three changed outcomes measurably. All verified every time, stayed in scope and kept the repo's tests passing. primer-mcp had slightly more functional passes, but the difference is within noise at this size.

The cost is about 50% more turns, time and spend, mostly on features (+60%). This likely overstates it in practice: each run started with no tickets, so every plan included setting up an epic, which an ongoing project does once. Wherever the agent planned, the overhead was about 15–25 extra turns, from a trivial change to a feature. It grows with the number of tickets created (about 2–3 primer-mcp calls per ticket) rather than with the size of the code change, so it should be a smaller share of larger work (untested here).

**Limits.**
- One model (`claude-sonnet-5`), one CLI version, one small clean codebase written for the eval. Three repetitions per scenario. How closely an agent follows a one-line instruction depends on the model.
- The arms didn't all run on the same days. The CLI version and model name were pinned throughout, but the model served behind that name could have changed in between.
- The planning metrics show that planning happened and was written down, not that it was necessarily good or well organised. The comparison of plan files with tickets above is a keyword search checked by reading, not a scored metric. The functional checks are narrow; one false negative is noted above.
- Whether to plan a small change is left to the agent's judgement, so the bug-fix and trivial results in particular may differ with another model.
- Every run was told no one would answer questions, so this says nothing about how primer-mcp's nudges to propose tickets play out with a user present, who can decline them.
- The eval models adopting primer-mcp on an app that already exists, with an empty `primer/` folder. In the intended use, from a project's start, epics and a standing bug-fix story would usually exist already. That affects both the setup cost above and whether the agent tracks small fixes, which this design cannot show.
- Each run is a single session, and nothing reads the tickets and decision records afterwards, so the eval measures what writing the record costs, not whether it pays off in later sessions.

## Next experiments

Each follows from a limit above.
- **Does the record pay off?** Two sessions per scenario: the first makes a change and records a decision; the second, starting fresh, gets a request that touches that decision. Measure whether the decision is respected, how many turns the agent spends working out context, and whether the result is correct. Compare primer-mcp with the saved-plan instruction plus commits, so that plan files and git history are the record to beat.
- **An established project.** Start the primer arm from a `primer/` folder that already has epics and a standing bug-fix story. That measures the ongoing cost rather than first use, and whether small fixes get tracked once there is somewhere to put them.
- **Another model.** A pilot-sized run (one per scenario per arm) with a more capable model, looking mostly at the bug-fix and trivial scenarios, where planning is a judgement call.

## Engineering notes

Problems solved along the way, recorded in the tickets under [`primer/tasks/`](primer/tasks/):
- **Isolation.** Each run must see only its own copy of the app. It runs in a fresh git repo under `/tmp`, with an empty `HOME`, a minimal environment and only its arm's MCP servers. This was learned the hard way: the first real run was inside this repo, where an agent could search parent folders for the reference solutions, and Claude Code picked up this repo's `CLAUDE.md`. That run was redone, and an automatic check now fails any run that loads something it shouldn't or touches this repo.
- **Pinning.** Claude Code auto-updated mid-day while the pilot was being set up, so the runner calls the pinned binary directly with the updater off, and every run records its versions. When the pinned build was no longer installed, it was reinstalled from Anthropic's release server and checked against its SHA-256.
- **Checks that can be trusted.** `validate_scenarios.py` confirms that every functional check fails on the app as shipped and passes with the reference solution.
- **Deterministic scoring, frozen before the headline.** No model judges the runs; Claude Code was used only to inspect transcripts and explain failures. Inspecting the pilot's transcripts found three scoring flaws (an unstated trap in one check, false scope violations, and read-only primer-mcp calls counted as planning), all fixed before the headline. The rules were then frozen, which is why the headline's one false negative is disclosed rather than rescored.
- **Statistics.** The 95% intervals come from resampling whole scenarios many times (a bootstrap). Runs of the same scenario behave alike, so the real sample is 12 scenarios, not 36 runs, and the intervals reflect that.
- **Testing the harness for free.** The scripts are tested against a fake `claude` that mimics its output, so they can be checked without paid runs. To make sure the fake matched reality, the real CLI was started once without a login: it printed what it had loaded, then stopped before any paid call. That real output is kept as test data.
- **Unattended batches.** Finished runs are skipped on restart, `--redo-failed` reruns failures, and `--wait-on-limit` waits out subscription usage limits. The headline batch hit one overnight and resumed.

## Reproducing

```
python3 scripts/validate_scenarios.py                                   # scenarios are well formed
python3 scripts/run_eval.py --batch pilot --dry-run                     # what each run would do
python3 scripts/run_eval.py --batch headline --reps 3 --wait-on-limit   # real runs; waits out usage limits (see scripts/README.md for auth)
python3 scripts/run_eval.py --batch headline --reps 3 --redo-failed     # rerun infrastructure failures
python3 scripts/score.py --batch headline                               # results/headline/summary.md
uv run --with pytest --no-project pytest tests                          # offline tests of the scripts
```
