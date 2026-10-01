# primer-mcp-eval

Does [primer-mcp](https://github.com/ivanlai/primer-mcp) change how AI coding agents work?

**At a glance.**
- **Question:** does primer-mcp, a planning-first MCP server, change how an AI coding agent works?
- **Design:** 12 change requests on an app written for the eval, given to headless Claude Code with and without primer-mcp, 3 times each: 72 isolated runs at pinned versions, scored deterministically from transcripts with no LLM judge.
- **Result:** on features and open-ended requests, primer-mcp took a written plan before coding from 0 of 15 runs to 15 of 15. On bug fixes and refactors it changed little. Outcomes (functional checks, tests, scope) showed no measurable difference. It cost about 50% more, partly one-off setup.
- **Follow-up:** a third arm with only "Plan first." in CLAUDE.md made the agent state a plan in chat before coding in 35 of 36 runs, at no extra cost, but it never wrote one down. What primer-mcp adds over that one line is the written record, not the planning.
- **Open question:** whether the written record pays off in later sessions, which this single-session design cannot show.

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

Prompts never mention primer-mcp, tickets or planning, and every arm gets identical prompts. Each prompt ends with one line saying no one is available to answer questions. Each scenario has a functional check, which asserts only what the prompt asks for, and a reference solution that proves the check can be passed. `scripts/validate_scenarios.py` confirms mechanically that every check fails on the app as shipped and passes with its reference.

**Arms** (ADR-003, ADR-006):
- *Baseline:* plain Claude Code with no MCP servers and no CLAUDE.md.
- *Primer:* the same, plus primer-mcp at a pinned version, with `init_project` already run (the `primer/` folder and its CLAUDE.md section are in place).
- *Instructions* (a follow-up, ADR-006): the baseline plus a CLAUDE.md that says only "Plan first." It tests the obvious objection: couldn't one line of instructions do what primer-mcp does?

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

primer-mcp-specific numbers (tickets created, `complete_task` and `verify_task` used) are reported for the primer arm only, because the baseline would score zero on them by construction.

**Runs** (ADR-005). A 24-run pilot (every scenario once per arm) tests the pipeline and the scoring rules against transcripts inspected with Claude Code. The headline is then 3 runs per scenario per arm (72 runs), with 95% intervals that treat the 12 scenarios, not the individual runs, as the sample (see Statistics under Engineering notes).

**Limits, stated up front.** The results describe Claude Code on one small, clean codebase. The planning metrics measure whether planning happened and was written down, not how good it was. Planning written only in chat text is not counted. Three runs per scenario can show large differences, not subtle ones.

## Results

**Headline** (72 runs: 12 scenarios × 2 arms × 3 repetitions, all at Claude Code 2.1.283, `claude-sonnet-5`, primer-mcp 0.1.7; every run passed the isolation check). Full tables: [`results/headline/summary.md`](results/headline/summary.md); per-run rows: [`results/headline/runs.csv`](results/headline/runs.csv).

| Metric | Baseline | primer-mcp |
|---|---|---|
| Wrote a plan before first code edit | 0% (0–0) | 53% (25–78) |
| Left a durable record | 0% (0–0) | 53% (25–78) |
| Verified before finishing | 100% | 100% |
| Functional pass | 89% (75–100) | 97% (92–100) |
| Repo's own tests pass | 100% | 100% |
| Stopped to ask | 0% | 0% |
| Out-of-scope files (mean) | 0 | 0 |
| Mean turns / time / est. cost | 19 / 66s / $0.29 | 30 / 101s / $0.44 |

The two planning metrics coincide because every primer-arm plan was a ticket. 95% intervals in brackets (how much each rate could vary by chance; see Statistics under Engineering notes). Cost is Claude Code's own API-equivalent estimate; the runs used a subscription, and the whole batch came to an estimated $26.

**By kind of change** (3 runs per scenario per arm):

| Kind | Wrote a plan before first code edit (baseline → primer) | Functional (baseline → primer) | Mean est. cost (baseline → primer) |
|---|---|---|---|
| Feature (4) | 0/12 → 12/12 | 9/12 → 11/12 | $0.45 → $0.72 |
| Ambiguous (1) | 0/3 → 3/3 | 2/3 → 3/3 | $0.40 → $0.74 |
| Bug fix (3) | 0/9 → 1/9 | 9/9 → 9/9 | $0.16 → $0.20 |
| Refactor (2) | 0/6 → 0/6 | 6/6 → 6/6 | $0.22 → $0.23 |
| Trivial (2) | 0/6 → 3/6 | 6/6 → 6/6 | $0.15 → $0.29 |

**What the runs show.**
- On every feature and ambiguous run, the primer-mcp agent created tickets before editing code and left them in the repo; the baseline never wrote a plan down. On bug fixes and refactors the two arms behaved similarly.
- In the one trivial scenario where it planned ("show a count per category"), each run set up the generic epic and standing bug-fix story that later small changes would go under ("Bug fixes & small improvements" and similar), then one task. Every run starts from an empty `primer/` folder, so every run paid this one-off setup, which more than doubled the cost of that scenario. In ongoing use it is paid once. The other trivial scenario (renaming a label) never used the tools.
- Of the 36 primer-arm runs, 21 called primer-mcp at least once. 19 created tickets (81 in all, about 4 per run), and 18 of those used both `complete_task` and `verify_task`. The other 2, both on the same bug fix, only listed the (empty) tickets and then fixed the bug without creating any.
- Functional failures (5 in all, each inspected with Claude Code):
  - *Budgets* (2 baseline, 1 primer): the summary didn't show the budget amount, which the prompt asked for.
  - *CSV import* (1 baseline): the error reported only the first bad line, not each one.
  - *Ambiguous request* (1 baseline): a flaw in the check, not the agent. The agent added a month-over-month comparison and fixed a real bug, but the check's data covers only one month, so the new line never appeared. It stays scored as a failure under the pre-set rules.

  While primer-mcp looks like a slight improvement, the gap (2 or 3 runs, depending on how the ambiguous case is counted) is too small to rule out statistical noise with a sample this size.
- The pilot's one stall (the agent stopped to ask for ticket approval despite being told no one would answer) did not recur in 36 primer runs.

**Follow-up: "Plan first." only** (36 runs, 12 scenarios × 3, run two days after the headline at the same pins, an estimated $10; every run passed the isolation check). Scored with the same frozen rules and compared with the headline runs above; the summary file now shows all three arms.

| Metric | Baseline | Instructions | primer-mcp |
|---|---|---|---|
| Wrote a plan before first code edit | 0% | 0% | 53% |
| Stated a plan in chat before first code edit | 0/36 | 35/36 | – |
| Left a durable record | 0% | 0% | 53% |
| Verified before finishing | 100% | 97% | 100% |
| Functional pass | 89% | 86% | 97% |
| Stopped to ask | 0% | 6% (2 runs) | 0% |
| Mean turns / time / est. cost | 19 / 66s / $0.29 | 18 / 70s / $0.28 | 30 / 101s / $0.44 |

The chat-plan row is not a scored metric (ADR-006 kept scoring deterministic): it comes from searching each run's messages before its first code edit for a stated plan, then reading the instructions-arm runs the search didn't match. In the baseline, no run used the word "plan" or listed numbered steps before editing. Planning written only in chat leaves nothing behind once the session ends, so it scores 0 on the written-plan and record metrics. primer-mcp's plans went into tickets, so that row doesn't apply to it.

- **The line works, in chat.** 35 of 36 runs set out a plan before touching code, usually a "Plan" heading with numbered steps, and several cited the instruction ("per CLAUDE.md's 'Plan first' instruction"). The other gave a one-sentence intent. Unlike primer-mcp, it planned on bug fixes and refactors too. None wrote the plan to a file, and none committed (the baseline didn't commit either; 10 of 36 primer runs did).
- **It costs nothing.** Turns, time and cost match the baseline. A chat plan is a few lines of output, where primer-mcp's tickets took about 15–25 extra turns.
- **It sometimes stalls.** In 2 runs (a bug fix and the CSV feature) the agent wrote its plan and then asked "Shall I proceed?", despite being told no one would answer, so nothing was built. That's the same failure the pilot saw once with primer-mcp, and it accounts for 2 of the 5 functional failures. The other 3 match the baseline's: the budget amount missing from the summary (2), and the ambiguous request's flawed check (1).
- One refactor run checked its output by running the CLI by hand instead of the tests, so it scores as unverified.

**Pilot** (24 runs, used to test the pipeline and scoring; not part of the headline): [`results/pilot/summary.md`](results/pilot/summary.md). It showed the same pattern.

## Verdict

primer-mcp changes how the agent works on larger pieces of work. On features and open-ended requests, adding it took planning-before-coding and a written record from never to every time, in 15 of 15 runs against 0 of 15. On bug fixes and refactors it made almost no difference, though that may change once a standing bug-fix story exists. What primer-mcp reliably adds is a written plan and record; whether that record pays for its cost over later sessions is the open question (see Limits).

**The "one line in CLAUDE.md" objection.** On this model, a single "Plan first." line gets the agent to plan before coding almost every time, at no cost, including on the small changes where primer-mcp mostly didn't plan. So primer-mcp's tools aren't needed to make the agent plan. What they add is the record: the plan written to the repo as linked tickets, decisions and verification notes, which outlives the session. That puts primer-mcp's value on whether a later session uses that record, which is the open question below.

It did not measurably change outcomes. Both arms verified every time, stayed in scope and kept the repo's tests passing. primer-mcp had slightly more functional passes, but the difference is within noise at this size.

The cost is about 50% more turns, time and spend, mostly on features (+60%). This likely overstates it in practice: each run started with no tickets, so every plan included setting up an epic, which an ongoing project does once. Wherever the agent planned, the overhead was about 15–25 extra turns, from a trivial change to a feature. It grows with the number of tickets created (about 2–3 primer-mcp calls per ticket) rather than with the size of the code change, so it should be a smaller share of larger work (untested here).

**Limits.**
- One model (`claude-sonnet-5`), one CLI version, one small clean codebase written for the eval. Three repetitions per scenario. How far an instruction alone goes depends on the model.
- The instructions arm ran two days after the other two, at the same pinned CLI version and model name; the model served behind that name could still have changed.
- The planning metrics show that planning happened and was written down, not that it was necessarily good. The functional checks are narrow; one false negative is noted above.
- Whether to plan a small change is left to the agent's judgement, so the bug-fix and trivial results in particular may differ with another model.
- Every run was told no one would answer questions, so this says nothing about how primer-mcp's nudges to propose tickets play out with a user present, who can decline them.
- The eval models adopting primer-mcp on an app that already exists, with an empty `primer/` folder. In the intended use, from a project's start, epics and a standing bug-fix story would usually exist already. That affects both the setup cost above and whether the agent tracks small fixes, which this design cannot show.
- Each run is a single session, and nothing reads the tickets and decision records afterwards, so the eval measures what writing the record costs, not whether it pays off in later sessions.

## Next experiments

Each follows from a limit above.
- **Does the record pay off?** Two sessions per scenario: the first makes a change and records a decision; the second, starting fresh, gets a request that touches that decision. Measure whether the decision is respected, how many turns the agent spends working out context, and whether the result is correct. Since "Plan first." already gets the planning, compare primer-mcp with "Plan first." plus commits, so git history is the record to beat.
- **An established project.** Start the primer arm from a `primer/` folder that already has epics and a standing bug-fix story. That measures the ongoing cost rather than first use, and whether small fixes get tracked once there is somewhere to put them.
- **Another model.** A pilot-sized run (one per scenario per arm) with a more capable model, looking mostly at the bug-fix and trivial scenarios, where planning is a judgement call.

## Engineering notes

Problems solved along the way, recorded in the tickets under [`primer/tasks/`](primer/tasks/):
- **Isolation.** Each run must see only its own copy of the app. It runs in a fresh git repo under `/tmp`, with an empty `HOME`, a minimal environment and only its arm's MCP servers. This was learned the hard way: the first real run was inside this repo, where an agent could search parent folders for the reference solutions, and Claude Code picked up this repo's `CLAUDE.md`. That run was redone, and an automatic check now fails any run that loads something it shouldn't or touches this repo.
- **Pinning.** Claude Code auto-updated mid-day while the pilot was being set up, so the runner calls the pinned binary directly with the updater off, and every run records its versions. By the follow-up the pinned version was no longer installed; it was reinstalled from Anthropic's release server, checked against the release's SHA-256, so the new arm could be compared with the existing runs instead of rerunning them.
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
