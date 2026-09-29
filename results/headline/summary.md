# Results: headline

72 runs.

## Rates by arm

| Metric | baseline | primer |
|---|---|---|
| planned_first | 0% (0%–0%) | 53% (25%–78%) |
| durable_record | 0% (0%–0%) | 53% (25%–78%) |
| verified | 100% (100%–100%) | 100% (100%–100%) |
| functional | 89% (75%–100%) | 97% (92%–100%) |
| repo_tests | 100% (100%–100%) | 100% (100%–100%) |
| asked | 0% (0%–0%) | 0% (0%–0%) |
| out-of-scope files (mean) | 0.00 | 0.00 |
| cost $ (mean) | 0.29 | 0.44 |
| turns (mean) | 18.94 | 29.78 |
| duration s (mean) | 66.12 | 101.09 |

Rates exclude runs where the metric doesn't apply. Intervals are 95%,
bootstrapped over scenarios.

## Per-scenario difference (primer − baseline)

| Scenario | planned_first | durable_record | verified | functional |
|---|---|---|---|---|
| ambiguous-summary | +100% | +100% | +0% | +33% |
| bug-category-filter-case | +0% | +0% | +0% | +0% |
| bug-float-amounts | +0% | +0% | +0% | +0% |
| bug-month-ignores-year | +33% | +33% | +0% | +0% |
| feature-budgets | +100% | +100% | +0% | +33% |
| feature-csv | +100% | +100% | +0% | +33% |
| feature-edit-delete | +100% | +100% | +0% | +0% |
| feature-recurring | +100% | +100% | +0% | +0% |
| refactor-render-summary | +0% | +0% | +0% | +0% |
| refactor-serialisation | +0% | +0% | +0% | +0% |
| trivial-average-label | +0% | +0% | +0% | +0% |
| trivial-category-counts | +100% | +100% | +0% | +0% |

## primer-mcp adoption (primer arm only, not compared)

- Runs that called any primer-mcp tool: 21/36
- Tickets created per run (mean): 2.25
- Runs using both complete_task and verify_task: 18/36
