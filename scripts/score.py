"""Score saved eval runs against the ADR-004 metrics and aggregate them (ADR-005).

Reads runs/<batch>/<scenario>/<arm>/r<n>/ (transcript.jsonl, meta.json, repo/) and writes
results/<batch>/runs.csv (one row per run) and results/<batch>/summary.md. No model calls.

Metric rules (the hand-read sample in the pilot checks these):
- code edit: an Edit/Write/MultiEdit/NotebookEdit tool call on a file that is not Markdown.
  Edits made through Bash (sed -i, redirection) are not seen; the pilot checks how often.
- planned_first: before the first code edit, the session called an in-session planning
  tool (TodoWrite, TaskCreate, TaskUpdate; headless 2.1.283 lists none of them up front),
  the built-in Plan agent (Task with subagent_type "Plan"), a primer-mcp tool that creates
  or records a ticket (reading tools such as list_tickets don't count), or wrote a
  Markdown file. A plan written only as chat text does not count. Blank when no code edit.
- durable_record: the final repo has a Markdown file added or changed since the initial
  commit (committed or not). primer tickets, ADRs and plan or notes documents all count.
- verified: a Bash call running pytest came after the last code edit. Blank when no edit.
- out_of_scope: number of changed files, other than Markdown, tests/ and primer/ (the
  ticket store and its generated graph), matching none of the scenario's expected_files.
- functional: the scenario's check passes on a copy of the final repo. repo_tests records
  whether the repo's own suite (as the agent left it) also passes.
- asked: the run made no code edit and its final message contains a question.
- cost_usd, turns, duration_s: from the result event (duration falls back to meta.json).

Usage: python3 scripts/score.py --batch pilot [--runs-dir DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import random
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_scenarios import SCENARIOS, pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PLAN_TOOLS = {"TodoWrite", "TaskCreate", "TaskUpdate"}
PRIMER_PLANNING = {"plan_epic", "record_adr", "create_story", "create_task", "create_spike"}
RATE_METRICS = ["planned_first", "durable_record", "verified", "functional", "repo_tests", "asked"]
FIELDS = [
    "scenario", "kind", "arm", "rep", *RATE_METRICS, "out_of_scope",
    "cost_usd", "turns", "duration_s", "primer_calls", "tickets_created", "complete_and_verify",
]  # fmt: skip


def events(transcript: Path) -> list[dict]:
    out = []
    for line in transcript.read_text().splitlines() if transcript.is_file() else []:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def tool_calls(evs: list[dict]) -> list[dict]:
    calls = []
    for e in evs:
        if e.get("type") == "assistant":
            for block in e.get("message", {}).get("content", []) or []:
                if block.get("type") == "tool_use":
                    calls.append(block)
    return calls


def edited_path(call: dict) -> str | None:
    if call.get("name") in EDIT_TOOLS:
        inp = call.get("input", {})
        return inp.get("file_path") or inp.get("notebook_path")
    return None


def is_markdown(path: str) -> bool:
    return path.lower().endswith(".md")


def is_code_edit(call: dict) -> bool:
    path = edited_path(call)
    return path is not None and not is_markdown(path)


def is_planning(call: dict) -> bool:
    name = call.get("name", "")
    path = edited_path(call)
    return (
        name in PLAN_TOOLS
        or (name == "Task" and call.get("input", {}).get("subagent_type") == "Plan")
        or name.removeprefix("mcp__primer-mcp__") in PRIMER_PLANNING
        or (path is not None and is_markdown(path))
    )


def runs_pytest(call: dict) -> bool:
    return call.get("name") == "Bash" and "pytest" in call.get("input", {}).get("command", "")


def changed_files(repo: Path) -> list[str]:
    """Files added, changed or deleted since the initial commit, including untracked ones."""

    def git(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout
        return [line for line in out.splitlines() if line]

    root = git("rev-list", "--max-parents=0", "HEAD")
    if not root:
        return []
    files = set(git("diff", "--name-only", root[0]))
    files |= set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(files)


def check_result(repo: Path, scenario: str) -> tuple[bool, bool]:
    """(scenario check passes, repo's own tests pass) on a scratch copy of the final repo."""
    checks = list((SCENARIOS / scenario).glob("test_*.py"))
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(
            repo, copy, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache")
        )
        check = pytest(copy, "--confcutdir", str(SCENARIOS), str(checks[0])) == "passed"
        suite = pytest(copy) == "passed"
    return check, suite


def score_run(run_dir: Path) -> dict:
    meta = json.loads((run_dir / "meta.json").read_text())
    scenario, arm = meta["scenario"], meta["arm"]
    spec = tomllib.loads((SCENARIOS / scenario / "scenario.toml").read_text())
    evs = events(run_dir / "transcript.jsonl")
    calls = tool_calls(evs)
    result = next((e for e in reversed(evs) if e.get("type") == "result"), {})
    repo = run_dir / "repo"

    code_edits = [i for i, c in enumerate(calls) if is_code_edit(c)]
    first, last = (code_edits[0], code_edits[-1]) if code_edits else (None, None)
    changed = changed_files(repo)
    out_of_scope = [
        f
        for f in changed
        if not is_markdown(f)
        and not f.startswith(("tests/", "primer/"))
        and not any(fnmatch.fnmatch(f, g) for g in spec["expected_files"])
    ]
    functional, repo_tests = check_result(repo, scenario)
    final_text = result.get("result", "") or ""
    primer_calls = [c["name"] for c in calls if c.get("name", "").startswith("mcp__primer-mcp__")]

    return {
        "scenario": scenario,
        "kind": spec["kind"],
        "arm": arm,
        "rep": run_dir.name,
        "planned_first": None if first is None else any(is_planning(c) for c in calls[:first]),
        "durable_record": any(is_markdown(f) for f in changed),
        "verified": None if last is None else any(runs_pytest(c) for c in calls[last + 1 :]),
        "functional": functional,
        "repo_tests": repo_tests,
        "asked": first is None and "?" in final_text,
        "out_of_scope": len(out_of_scope),
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
        "duration_s": round(result["duration_ms"] / 1000, 1)
        if "duration_ms" in result
        else meta.get("duration_s"),
        "primer_calls": len(primer_calls),
        "tickets_created": sum(1 for f in changed if f.startswith("primer/") and is_markdown(f)),
        "complete_and_verify": any(n.endswith("__complete_task") for n in primer_calls)
        and any(n.endswith("__verify_task") for n in primer_calls),
    }


def rate(rows: list[dict], metric: str) -> float | None:
    values = [r[metric] for r in rows if r[metric] is not None]
    return sum(values) / len(values) if values else None


def bootstrap_ci(rows: list[dict], metric: str, n: int = 2000, seed: int = 0):
    """95% interval for a rate, resampling scenarios (runs of one scenario are correlated)."""
    by_scenario: dict[str, list[dict]] = {}
    for r in rows:
        by_scenario.setdefault(r["scenario"], []).append(r)
    names = sorted(by_scenario)
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        sample = [r for s in rng.choices(names, k=len(names)) for r in by_scenario[s]]
        value = rate(sample, metric)
        if value is not None:
            stats.append(value)
    if not stats:
        return None
    stats.sort()
    return stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]


def fmt(value, pct: bool = True) -> str:
    if value is None:
        return "–"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def summary(rows: list[dict], batch: str) -> str:
    arms = sorted({r["arm"] for r in rows})
    by_arm = {a: [r for r in rows if r["arm"] == a] for a in arms}
    lines = [f"# Results: {batch}", "", f"{len(rows)} runs.", "", "## Rates by arm", ""]
    lines += ["| Metric | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for m in RATE_METRICS:
        cells = []
        for a in arms:
            ci = bootstrap_ci(by_arm[a], m)
            cells.append(fmt(rate(by_arm[a], m)) + (f" ({fmt(ci[0])}–{fmt(ci[1])})" if ci else ""))
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    for m, label in [("out_of_scope", "out-of-scope files (mean)"), ("cost_usd", "cost $ (mean)"),
                     ("turns", "turns (mean)"), ("duration_s", "duration s (mean)")]:  # fmt: skip
        cells = []
        for a in arms:
            vals = [r[m] for r in by_arm[a] if r[m] is not None]
            cells.append(fmt(sum(vals) / len(vals), pct=False) if vals else "–")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "Rates exclude runs where the metric doesn't apply. Intervals are 95%,",
              "bootstrapped over scenarios.", ""]  # fmt: skip

    if len(arms) == 2:
        lines += ["## Per-scenario difference (" + f"{arms[1]} − {arms[0]})", ""]
        head = ["planned_first", "durable_record", "verified", "functional"]
        lines += ["| Scenario | " + " | ".join(head) + " |", "|---|" + "---|" * len(head)]
        for s in sorted({r["scenario"] for r in rows}):
            cells = []
            for m in head:
                a, b = (rate([r for r in by_arm[x] if r["scenario"] == s], m) for x in arms)
                cells.append("–" if a is None or b is None else f"{b - a:+.0%}")
            lines.append(f"| {s} | " + " | ".join(cells) + " |")
        lines.append("")

    primer = by_arm.get("primer", [])
    if primer:
        lines += ["## primer-mcp adoption (primer arm only, not compared)", ""]
        used = sum(1 for r in primer if r["primer_calls"])
        lines.append(f"- Runs that called any primer-mcp tool: {used}/{len(primer)}")
        lines.append(
            f"- Tickets created per run (mean): {fmt(rate(primer, 'tickets_created'), False)}"
        )
        both = sum(1 for r in primer if r["complete_and_verify"])
        lines.append(f"- Runs using both complete_task and verify_task: {both}/{len(primer)}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score saved eval runs.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--out", type=Path, default=ROOT / "results")
    args = parser.parse_args(argv)

    run_dirs = sorted(p.parent for p in (args.runs_dir / args.batch).glob("*/*/r*/meta.json"))
    if not run_dirs:
        sys.exit(f"no runs under {args.runs_dir / args.batch}")
    rows = [score_run(d) for d in run_dirs]
    out = args.out / args.batch
    out.mkdir(parents=True, exist_ok=True)
    with (out / "runs.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out / "summary.md").write_text(summary(rows, args.batch))
    print(f"scored {len(rows)} runs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
