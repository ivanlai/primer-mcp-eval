import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_eval  # noqa: E402
import score  # noqa: E402

SCENARIO = "bug-float-amounts"
STUB = str(Path(__file__).resolve().parent / "stub_claude.py")


def call(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


def make_run(tmp_path, calls, arm="baseline", result_text="Done.", patch=False, extra=None):
    """A saved run: fixture repo (optionally with the reference fix), transcript and meta."""
    run_dir = tmp_path / "pilot" / SCENARIO / arm / "r1"
    repo = run_dir / "repo"
    run_eval.prepare_repo(repo, "baseline", "0.1.7")
    if patch:
        ref = run_eval.SCENARIOS / SCENARIO / "reference.patch"
        subprocess.run(["git", "apply", str(ref)], cwd=repo, check=True)
    for rel, text in (extra or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    lines = [{"type": "system", "subtype": "init", "tools": [], "mcp_servers": []}]
    lines += [{"type": "assistant", "message": {"content": [c]}} for c in calls]
    lines.append(
        {
            "type": "result",
            "result": result_text,
            "total_cost_usd": 0.5,
            "num_turns": 7,
            "duration_ms": 42000,
        }  # fmt: skip
    )
    (run_dir / "transcript.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    meta = {"scenario": SCENARIO, "arm": arm, "duration_s": 50.0}
    (run_dir / "meta.json").write_text(json.dumps(meta))
    return run_dir


def test_planning_tool_before_first_edit_counts(tmp_path):
    run = make_run(tmp_path, [call("TodoWrite"), call("Edit", file_path="src/expenses/models.py")])
    assert score.score_run(run)["planned_first"] is True


def test_planning_after_first_edit_does_not_count(tmp_path):
    run = make_run(tmp_path, [call("Edit", file_path="src/expenses/models.py"), call("TodoWrite")])
    assert score.score_run(run)["planned_first"] is False


def test_primer_tool_or_markdown_write_counts_as_planning(tmp_path):
    edit = call("Edit", file_path="/abs/repo/src/expenses/models.py")
    primer = make_run(tmp_path / "a", [call("mcp__primer-mcp__create_task"), edit])
    notes = make_run(tmp_path / "b", [call("Write", file_path="/abs/repo/PLAN.md"), edit])
    assert score.score_run(primer)["planned_first"] is True
    assert score.score_run(notes)["planned_first"] is True


def test_no_code_edit_means_planning_and_verification_not_applicable(tmp_path):
    run = make_run(tmp_path, [call("Read", file_path="src/expenses/models.py")])
    row = score.score_run(run)
    assert row["planned_first"] is None and row["verified"] is None


def test_verified_needs_pytest_after_last_edit(tmp_path):
    edit = call("Edit", file_path="src/expenses/models.py")
    test = call("Bash", command="uv run pytest -q")
    after = make_run(tmp_path / "a", [edit, test])
    before = make_run(tmp_path / "b", [test, edit])
    assert score.score_run(after)["verified"] is True
    assert score.score_run(before)["verified"] is False


def test_reference_fix_is_functional_and_in_scope(tmp_path):
    run = make_run(tmp_path, [call("Edit", file_path="src/expenses/models.py")], patch=True)
    row = score.score_run(run)
    assert row["functional"] is True and row["repo_tests"] is True
    assert row["out_of_scope"] == 0 and row["durable_record"] is False


def test_untouched_repo_is_not_functional(tmp_path):
    assert score.score_run(make_run(tmp_path, []))["functional"] is False


def test_markdown_is_a_durable_record_and_other_files_are_out_of_scope(tmp_path):
    extra = {"NOTES.md": "decided X\n", "src/expenses/cli.py": "# changed\n", "tests/test_x.py": ""}
    row = score.score_run(make_run(tmp_path, [], extra=extra))
    assert row["durable_record"] is True
    assert row["out_of_scope"] == 1  # cli.py; the note and tests/ are not counted


def test_asked_means_no_code_edit_and_a_question(tmp_path):
    asked = make_run(tmp_path / "a", [], result_text="Which currency should I use?")
    worked = make_run(
        tmp_path / "b", [call("Edit", file_path="src/x.py")], result_text="Fixed. Anything else?"
    )
    assert score.score_run(asked)["asked"] is True
    assert score.score_run(worked)["asked"] is False


def test_cost_and_turns_come_from_the_result_event(tmp_path):
    row = score.score_run(make_run(tmp_path, []))
    assert (row["cost_usd"], row["turns"], row["duration_s"]) == (0.5, 7, 42.0)


def test_primer_adoption_stats(tmp_path):
    calls = [call("mcp__primer-mcp__complete_task"), call("mcp__primer-mcp__verify_task")]
    run = make_run(tmp_path, calls, arm="primer", extra={"primer/tasks/TK-001.md": "x"})
    row = score.score_run(run)
    assert row["primer_calls"] == 2 and row["tickets_created"] == 1
    assert row["complete_and_verify"] is True


def test_bootstrap_resamples_scenarios_and_brackets_the_rate():
    rows = [{"scenario": f"s{i}", "m": i % 2 == 0} for i in range(10)]
    lo, hi = score.bootstrap_ci(rows, "m")
    assert lo <= score.rate(rows, "m") <= hi
    assert score.bootstrap_ci(rows, "m") == (lo, hi)  # seeded, so reproducible
    assert score.bootstrap_ci([{"scenario": "s", "m": None}], "m") is None


def test_end_to_end_on_stub_runs(tmp_path):
    runs = tmp_path / "runs"
    run_eval.main(
        [
            "--batch",
            "pilot",
            "--scenario",
            "trivial-average-label",
            "--claude",
            STUB,
            "--runs-dir",
            str(runs),
        ]  # fmt: skip
    )
    assert score.main(["--batch", "pilot", "--runs-dir", str(runs), "--out", str(tmp_path)]) == 0
    csv_text = (tmp_path / "pilot" / "runs.csv").read_text()
    assert csv_text.count("\n") == 3  # header + one run per arm
    summary = (tmp_path / "pilot" / "summary.md").read_text()
    assert "## Rates by arm" in summary and "primer-mcp adoption" in summary


def test_plan_agent_counts_as_planning(tmp_path):
    calls = [
        call("Task", subagent_type="Plan", prompt="plan it"),
        call("Edit", file_path="src/a.py"),
    ]
    assert score.score_run(make_run(tmp_path, calls))["planned_first"] is True
    other = [call("Task", subagent_type="Explore"), call("Edit", file_path="src/a.py")]
    assert score.score_run(make_run(tmp_path / "b", other))["planned_first"] is False
