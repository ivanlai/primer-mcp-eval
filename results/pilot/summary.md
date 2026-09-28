# Results: pilot

24 runs.

## Rates by arm

| Metric | baseline | primer |
|---|---|---|
| planned_first | 0% (0%–0%) | 45% (17%–75%) |
| durable_record | 0% (0%–0%) | 42% (17%–67%) |
| verified | 100% (100%–100%) | 100% (100%–100%) |
| functional | 100% (100%–100%) | 92% (75%–100%) |
| repo_tests | 100% (100%–100%) | 100% (100%–100%) |
| asked | 0% (0%–0%) | 8% (0%–25%) |
| out-of-scope files (mean) | 0.00 | 0.00 |
| cost $ (mean) | 0.28 | 0.41 |
| turns (mean) | 18.33 | 28.58 |
| duration s (mean) | 61.88 | 84.65 |

Rates exclude runs where the metric doesn't apply. Intervals are 95%,
bootstrapped over scenarios.

## Per-scenario difference (primer − baseline)

| Scenario | planned_first | durable_record | verified | functional |
|---|---|---|---|---|
| ambiguous-summary | +100% | +100% | +0% | +0% |
| bug-category-filter-case | +0% | +0% | +0% | +0% |
| bug-float-amounts | +0% | +0% | +0% | +0% |
| bug-month-ignores-year | +0% | +0% | +0% | +0% |
| feature-budgets | +100% | +100% | +0% | +0% |
| feature-csv | +100% | +100% | +0% | +0% |
| feature-edit-delete | +100% | +100% | +0% | +0% |
| feature-recurring | +100% | +100% | +0% | +0% |
| refactor-render-summary | +0% | +0% | +0% | +0% |
| refactor-serialisation | +0% | +0% | +0% | +0% |
| trivial-average-label | +0% | +0% | +0% | +0% |
| trivial-category-counts | – | +0% | – | -100% |

## primer-mcp adoption (primer arm only, not compared)

- Runs that called any primer-mcp tool: 8/12
- Tickets created per run (mean): 1.83
- Runs using both complete_task and verify_task: 5/12
