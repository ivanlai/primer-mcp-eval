import json
from datetime import datetime
import sys
from pathlib import Path

import pytest

pytest.importorskip("inspect_ai")
from inspect_ai.log import read_eval_log  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_inspect  # noqa: E402
import score  # noqa: E402
from test_score import make_run  # noqa: E402


def test_export_carries_transcript_and_frozen_scores(tmp_path):
    run_dir = make_run(tmp_path, [], patch=True)
    meta = json.loads((run_dir / "meta.json").read_text())
    meta |= {"pins": {"model": "claude-sonnet-5"}, "limits": {}}
    (run_dir / "meta.json").write_text(json.dumps(meta))
    (run_dir / "prompt.txt").write_text("Fix the rounding.")
    lines = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {"type": "assistant", "timestamp": "2026-09-29T00:00:00.000Z",
         "message": {"id": "m1", "content": [{"type": "text", "text": "Looking."}]}},
        {"type": "assistant", "message": {"id": "m1", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "1 passed"}]}},
        {"type": "assistant", "message": {"id": "m1", "content": [
            {"type": "tool_use", "id": "t2", "name": "ToolSearch", "input": {"query": "primer"}}]}},
        {"type": "user", "timestamp": "2026-09-29T00:00:42.000Z", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": [
            {"type": "tool_reference", "tool_name": "mcp__primer-mcp__create_story"}]}]}},
        {"type": "result", "result": "Fixed.", "total_cost_usd": 0.5, "num_turns": 3,
         "duration_ms": 42000},
    ]  # fmt: skip
    (run_dir / "transcript.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    assert score.main(["--batch", "pilot", "--runs-dir", str(tmp_path), "--out", str(tmp_path / "res")]) == 0  # fmt: skip

    assert export_inspect.main(["--batch", "pilot", "--runs-dir", str(tmp_path),
                         "--results-dir", str(tmp_path / "res"), "--out", str(tmp_path / "logs")]) == 0  # fmt: skip

    log = read_eval_log(str(tmp_path / "logs" / "pilot" / "inspect" / "baseline.eval"))
    [s] = log.samples
    assert s.id == "bug-float-amounts/r1"
    roles = [m.role for m in s.messages]
    assert roles == ["user", "assistant", "tool", "tool"]  # all m1 events merge into one message
    assert s.messages[1].text == "Looking."
    assert [c.function for c in s.messages[1].tool_calls] == ["Bash", "ToolSearch"]
    assert s.messages[2].function == "Bash" and s.messages[2].text == "1 passed"
    assert s.messages[3].text == "mcp__primer-mcp__create_story"  # tool_reference shown by name
    assert s.scores["functional"].value == "C"
    assert "planned_first" not in s.scores  # no code edit, so not applicable
    assert s.metadata["cost_usd"] == 0.5
    assert s.output.completion == "Fixed."
    started, completed = (
        datetime.fromisoformat(str(t)) for t in (log.stats.started_at, log.stats.completed_at)
    )
    assert (completed - started).total_seconds() == 42  # header duration: first to last event
