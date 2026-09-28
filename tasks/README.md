# Tasks

The coding tasks each eval run gives the agent (ADR-001). One directory per task; a directory is a task if it holds a `task.toml`.

```
tasks/
  autonomy.txt        shared line appended to every prompt (ADR-003)
  conftest.py         shared `run` fixture: drives the fixture CLI on a fresh data file
  <task-id>/
    prompt.md         the request, exactly as a user would write it
    task.toml         kind and expected_files
    test_<id>.py      functional check (ADR-004)
    reference.patch   a known-good solution, relative to the fixture root
```

## Prompt

The agent receives `prompt.md`, a blank line, then `autonomy.txt`. Prompts describe what the user sees or wants, never the cause or the fix, and never mention primer-mcp, tickets, planning, tests or commits. Both arms get identical prompts.

## task.toml

```toml
kind = "bug"                                   # feature | bug | refactor | trivial | ambiguous
expected_files = ["src/expenses/reports.py"]   # paths relative to the fixture root
```

`expected_files` lists the source files a reasonable solution changes, for the scope metric. Entries may be glob patterns (`src/expenses/*.py`) where a solution may add modules whose names can't be known in advance. Files under `tests/` are always in scope, and planning or notes files are scored separately (ADR-004), so neither is listed here.

## Checks

Checks drive only the CLI (`expenses.cli.main`), so a fix that restructures the internals is still judged on behaviour. A check asserts only what the prompt states: it is a guardrail that the work was done (ADR-004), not a hunt for edge cases, and every unstated trap is a way for a reasonable solution to fail. Run a check from the root of a fixture copy:

```
uv run pytest -p no:cacheprovider --confcutdir=<repo>/tasks <repo>/tasks/<task-id>
```

`--confcutdir` is needed so pytest loads `tasks/conftest.py`, which sits outside the fixture copy's rootdir.

A task is valid when its check fails on the fixture as shipped, and when, with `reference.patch` applied, both the check and the fixture's own suite pass.

Validate every task (or name task ids) with `python3 scripts/validate_tasks.py`. It exports the fixture from git HEAD, so commit fixture changes first.
