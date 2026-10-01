# primer-mcp-eval

Does [primer-mcp](https://github.com/ivanlai/primer-mcp) change how AI coding agents work?

**Summary**

12 coding requests on a small app, given to Claude Code three ways. Each request ran 3 times per setup, 108 runs in all, scored automatically with no AI judge.

| Setup | Wrote a plan down before coding | Extra cost |
|---|---|---|
| Plain | never | – |
| One line in CLAUDE.md asking for a saved plan | on every request (36 of 36) | about 7% |
| primer-mcp | on every feature and open-ended request (15 of 15) | about 50% |

None of the three changed whether the work was done correctly.

- **Why the one line scores higher:** it asks for a plan on every change, with no exceptions. primer-mcp deliberately doesn't. Its guidance says to skip steps when they don't make sense, and to put small fixes under a shared "bug fixes" story. On one-line fixes the agent took that option and just made the fix.
- **What primer-mcp adds:** not the plan itself, since one line gets that. It adds a more structured record:
  - goals kept apart from implementation steps,
  - decisions with the options that were rejected, and
  - a status for each piece of work. 
 
  The plan files had none of these.
- **Open question:** whether that structure helps later work. The case for it is the usual case for an issue tracker. This test can't measure it.

## What primer-mcp is

An MCP server that gives a coding agent ticket tools (epics, decisions, stories, tasks). It also adds a short CLAUDE.md section asking the agent to plan before coding, record decisions, and check its work before finishing.

The claim is that the agent:
- plans first,
- leaves a written record,
- verifies its work, and
- stays in scope.

This repo tests that claim on a small scale.

## How the test works

The design decisions are recorded in [`primer/adrs/`](primer/adrs/). The eval is itself planned with primer-mcp.

**The app** ([`fixtures/app/`](fixtures/app/)). A small expense tracker in Python (about 600 lines with tests), written for this test so no agent has seen it before. It records expenses, lists them by month or category, and prints a monthly summary. It has a passing test suite and three planted bugs the tests don't catch.

**The requests** ([`scenarios/`](scenarios/)). Twelve changes, written the way a user would ask:

| Kind | # | Examples |
|---|---|---|
| Feature | 4 | edit and delete expenses; monthly budgets; CSV export and import; recurring expenses |
| Bug fix | 3 | "a 0.29 stamp shows as 0.28"; March includes last year's March; category filter is case-sensitive |
| Refactor | 2 | move the summary text into its own function; move JSON conversion out of the data class |
| Trivial | 2 | rename a label; show a count per category |
| Ambiguous | 1 | "Make `expenses summary` more useful." |

Every request:
- uses the same wording in every setup, and never mentions planning, tickets or primer-mcp;
- ends with a line saying no one is available to answer questions;
- has an automatic check of the result, and a reference solution that proves the check can be passed (`scripts/validate_scenarios.py` confirms this).

**The three setups:**
- *Baseline:* plain Claude Code, no MCP servers, no CLAUDE.md.
- *Instructions:* a CLAUDE.md with one line: "Plan first, and save the plan in docs/ before changing code."
- *Primer:* primer-mcp installed and set up (its `primer/` folder and CLAUDE.md section in place).

**Running.** Each run is a separate headless Claude Code session at fixed versions (`eval.toml`), in a fresh copy of the app, cut off from the developer's own setup (see [Engineering notes](#engineering-notes)).

**Scoring** (`scripts/score.py`). Worked out from each run's transcript and final files:

| Measure | Counts when |
|---|---|
| Wrote a plan first | a planning tool, a ticket or a Markdown file came before the first code change |
| Left a record | a Markdown file was added or changed in the repo |
| Verified | tests were run after the last code change |
| Stayed in scope | no files changed outside the ones the request needs |
| Worked | the request's check passes |
| Cost | turns, time and estimated cost |

A 24-run pilot first tested the pipeline and the scoring rules ([`results/pilot/summary.md`](results/pilot/summary.md)).

## Results

108 runs at Claude Code 2.1.283, `claude-sonnet-5`, primer-mcp 0.1.7. All passed the isolation check. Full tables: [`results/headline/summary.md`](results/headline/summary.md); one row per run: [`results/headline/runs.csv`](results/headline/runs.csv).

| | Baseline | Instructions | primer-mcp |
|---|---|---|---|
| Wrote a plan first | 0% | 100% | 53% |
| Left a record | 0% | 100% | 53% |
| Verified | 100% | 100% | 100% |
| Worked | 89% | 92% | 97% |
| Stayed in scope | 100% | 100% | 100% |
| App's own tests still pass | 100% | 100% | 100% |
| Turns / time / cost per run | 19 / 66s / $0.29 | 20 / 81s / $0.31 | 30 / 101s / $0.44 |

Costs are Claude Code's estimate at API prices (about $37 in all); the runs used a subscription.

**By kind of request** (baseline · instructions · primer-mcp):

| Kind | Wrote a plan first | Worked | Cost per run |
|---|---|---|---|
| Feature (4) | 0/12 · 12/12 · 12/12 | 9/12 · 9/12 · 11/12 | $0.45 · $0.46 · $0.72 |
| Ambiguous (1) | 0/3 · 3/3 · 3/3 | 2/3 · 3/3 · 3/3 | $0.40 · $0.40 · $0.74 |
| Bug fix (3) | 0/9 · 9/9 · 1/9 | 9/9 · 9/9 · 9/9 | $0.16 · $0.21 · $0.20 |
| Refactor (2) | 0/6 · 6/6 · 0/6 | 6/6 · 6/6 · 6/6 | $0.22 · $0.24 · $0.23 |
| Trivial (2) | 0/6 · 6/6 · 3/6 | 6/6 · 6/6 · 6/6 | $0.15 · $0.18 · $0.29 |

**What happened.**
- **primer-mcp** created tickets before coding on every feature and the ambiguous request. On bug fixes and refactors it mostly didn't.
  - That's by design: primer-mcp's guidance says to skip steps when they don't make sense, and to file small fixes under a shared "bug fixes" story.
  - No such story existed yet, and the agents said as much ("The fix was small enough… that I went ahead and applied it directly").
  - Several only thought about a ticket after the fix was done, as a record rather than a plan.
  - In one trivial request it set up an epic and a "bug fixes" story first, which doubled that request's cost. A real project pays that setup once.
- **The one-line instruction** was followed every time: one plan file in `docs/` before any code, on every kind of request, for a few extra turns (tickets took 15–25).
- **The plan files** were mostly a list of code changes under a short goal.
  - None recorded rejected options, acceptance criteria or a status.
  - None was updated after coding started.
  - Each run named its file differently.

  primer-mcp's tickets have places for all of these. How well they're filled in isn't scored, and the primer runs wrote only 4 decision records in all.
- **Failures** (8 in all):
  - *Budgets* (2 baseline, 3 instructions, 1 primer): the summary left out the budget amount the request asked for. In the instructions setup, all three plans left it out too, so the plan carried the mistake into the code.
  - *CSV import* (1 baseline): only the first bad line was reported.
  - *Ambiguous request* (1 baseline): the check's fault, not the agent's. The agent's new month-over-month line only shows with two months of data, which the check didn't have. It still counts as a failure, because the scoring rules were fixed in advance.

  primer-mcp's slightly higher success rate is within what chance could explain at this size.

## Verdict

primer-mcp changes how the agent works on larger tasks: it plans and writes the plan down, where the plain agent never did. But one line in CLAUDE.md does that too, on every kind of task, for much less.

What primer-mcp adds is the structure of what gets written: goals, decisions and status, kept apart.

This test checks whether a record exists, not whether its structure helps. There is a reasonable case that it does: primer-mcp's tickets work as a lightweight issue tracker, and few teams run anything beyond small work on plan files and git history alone.

But that case comes from teams of people working over months, and from records that people keep up to date. This test had a single session, nobody read the record afterwards, and the primer runs wrote only 4 decision records in all. Whether the structure is worth the extra cost for an agent is still open.

None of the setups changed whether the work was done correctly.

primer-mcp's extra cost (about 50%) is mostly ticket writing, roughly 2–3 tool calls per ticket.
- It grows with the number of tickets, not the size of the change, so it should matter less on larger work.
- It's overstated here, because every run started with no tickets and had to set up an epic first.

**Limits.**
- One model, one Claude Code version, one small, clean app, 3 runs per request. How closely an agent follows a one-line instruction depends on the model.
- The three setups didn't all run on the same days. Versions and the model name were fixed, but the model behind that name could have changed.
- The scores show that a plan was written, not that it was good. The comparison of plan files and tickets above comes from a keyword search checked by reading, not from the scoring.
- No one was there to answer questions, so this says nothing about how primer-mcp works with a user who can say no to tickets.
- Every primer run started with an empty ticket folder. In a real project, epics and a "bug fixes" story would usually exist, which affects both the cost and whether small fixes get tickets.

## Next experiments

- **Does the record pay off?** Two sessions per request. The first makes a change and a decision. The second starts fresh and gets a request that touches that decision.
  - Measure whether it respects the decision, how long it spends working out context, and whether it gets the result right.
  - Compare primer-mcp with the saved-plan instruction plus git commits, so plan files and git history are the record to beat.
- **An established project.** Start primer-mcp with existing epics and a "bug fixes" story, to measure the ongoing cost and whether small fixes get tracked.
- **Another model.** A small run with a more capable model on features and ambiguous requests, where primer-mcp is meant to be strongest. With this model the one line matched primer-mcp there. The check is whether that still holds, since how closely an agent follows a one-line instruction depends on the model.

## Engineering notes

Details are in the tickets under [`primer/tasks/`](primer/tasks/).
- **Isolation.** The first real run was inside this repo, where the agent could have found the reference solutions and picked up this repo's CLAUDE.md. Now each run:
  - works in a fresh git repo of the app under `/tmp`, outside this repo. Claude Code reads CLAUDE.md from parent folders, and an agent searching upwards must not find `scenarios/`;
  - gets an empty home folder and only a few environment variables plus a login token, so the developer's instructions, memory, skills, hooks, git config and MCP servers can't reach it;
  - loads MCP servers only from its own config (`--strict-mcp-config`): primer-mcp in the primer setup, none in the others.

  After each run, a check reads the session's startup event and its transcript. It fails the run if the session loaded any of the developer's skills or agents, a non-built-in plugin, memory from outside its home folder or the wrong MCP servers, or if it ran inside or mentioned this repo. All 108 runs passed.
- **Pinning.** Claude Code updated itself mid-day while the pilot was being set up, so the runner calls a fixed binary with updates turned off, and each run records its versions. When that binary was no longer installed, it was reinstalled from Anthropic's release server and checked against its published hash.
- **Trustworthy checks.** `validate_scenarios.py` confirms every check fails on the original app and passes with the reference solution.
- **Fixed scoring rules.** No AI judges the runs. Reading the pilot's transcripts found three scoring mistakes, all fixed before the main runs. The rules were then frozen, which is why the one unfair failure above is reported rather than rescored.
- **Statistics.** Runs of the same request behave alike, so the real sample is the 12 requests, not every run. The ranges come from resampling requests (a bootstrap).
- **Testing without spending.** The offline tests in [`tests/`](tests/) cover the runner and the scoring without calling the model.
  - A stub `claude` ([`tests/stub_claude.py`](tests/stub_claude.py)) answers like the real CLI in headless mode: it reports what it loaded at startup, makes one file edit and ends with a result. The runner tests use it to check each setup's repo, the empty home folder, skipping finished runs and rerunning failed ones.
  - A "leaky" mode makes the stub load an MCP server it shouldn't, to prove the isolation check catches it.
  - The startup event the check reads was captured once from the real CLI ([`tests/init_event_2.1.283.json`](tests/init_event_2.1.283.json)), without logging in, so the check is tested against the real format rather than a guess.
  - The scoring tests use small handmade transcripts, plus the stub's runs end to end.
- **Unattended runs.** Finished runs are skipped on restart, `--redo-failed` reruns failures, and `--wait-on-limit` waits out usage limits.

## Reproducing

```
python3 scripts/validate_scenarios.py                                   # check the scenarios
python3 scripts/run_eval.py --batch pilot --dry-run                     # show what each run would do
python3 scripts/run_eval.py --batch headline --reps 3 --wait-on-limit   # real runs (see scripts/README.md for login)
python3 scripts/run_eval.py --batch headline --reps 3 --redo-failed     # rerun failed runs
python3 scripts/score.py --batch headline                               # write results/headline/summary.md
uv run --with pytest --no-project pytest tests                          # test the scripts offline
```
