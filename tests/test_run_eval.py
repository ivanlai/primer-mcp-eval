import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_eval  # noqa: E402

STUB = str(Path(__file__).resolve().parent / "stub_claude.py")
SCENARIO = "trivial-average-label"


def run(tmp_path, *extra):
    return run_eval.main(
        ["--batch", "pilot", "--scenario", SCENARIO, "--claude", STUB, "--runs-dir", str(tmp_path)]
        + list(extra)
    )


def test_compose_prompt_appends_autonomy_line():
    prompt = run_eval.compose_prompt(SCENARIO)
    request = (run_eval.SCENARIOS / SCENARIO / "prompt.md").read_text().strip()
    autonomy = (run_eval.SCENARIOS / "autonomy.txt").read_text().strip()
    assert prompt == f"{request}\n\n{autonomy}\n"


def test_both_arms_produce_full_layout(tmp_path):
    assert run(tmp_path) == 0
    for arm in ("baseline", "primer"):
        d = tmp_path / "pilot" / SCENARIO / arm / "r1"
        for name in ("prompt.txt", "command.json", "transcript.jsonl", "stderr.txt", "meta.json"):
            assert (d / name).is_file(), (arm, name)
        meta = json.loads((d / "meta.json").read_text())
        assert meta["exit_code"] == 0 and meta["isolation_problems"] == []
        assert (d / "repo" / "stub_note.txt").is_file()
        log = subprocess.run(
            ["git", "log", "--format=%s"], cwd=d / "repo", capture_output=True, text=True
        )
        assert log.stdout.strip() == "Initial commit"


def test_primer_arm_is_initialised_and_baseline_is_not(tmp_path):
    run(tmp_path)
    base = tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "repo"
    primer = tmp_path / "pilot" / SCENARIO / "primer" / "r1" / "repo"
    assert not (base / "primer").exists() and not (base / "CLAUDE.md").exists()
    assert (primer / "primer" / "config.yaml").is_file()
    assert "primer-mcp" in (primer / "CLAUDE.md").read_text()
    tracked = subprocess.run(["git", "ls-files"], cwd=primer, capture_output=True, text=True)
    assert "CLAUDE.md" in tracked.stdout.split()


def test_session_gets_an_empty_home(tmp_path):
    run(tmp_path, "--arm", "baseline")
    transcript = tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "transcript.jsonl"
    init = json.loads(transcript.read_text().splitlines()[0])
    home = Path(init["home"])
    assert home != Path.home()
    assert "eval-home-" in home.name


def test_leaky_baseline_fails_isolation(tmp_path):
    leaky = tmp_path / "leaky_claude"
    leaky.write_text(f'#!/bin/sh\nSTUB_LEAKY=1 exec {STUB} "$@"\n')
    leaky.chmod(0o755)
    code = run_eval.main(
        ["--batch", "pilot", "--scenario", SCENARIO, "--arm", "baseline"]
        + ["--claude", str(leaky), "--runs-dir", str(tmp_path)]
    )
    assert code == 1
    meta = json.loads((tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "meta.json").read_text())
    assert meta["isolation_problems"]


def test_finished_runs_are_skipped(tmp_path, capsys):
    run(tmp_path, "--arm", "baseline")
    capsys.readouterr()
    run(tmp_path, "--arm", "baseline")
    assert "skip" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path, capsys):
    assert run(tmp_path, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "--strict-mcp-config" in out and "Average per day" in out
    assert not (tmp_path / "pilot").exists()


@pytest.mark.parametrize("arm", ["baseline", "primer"])
def test_mcp_config_per_arm(arm):
    servers = run_eval.mcp_config(arm, "0.1.7", "uvx")["mcpServers"]
    assert (arm == "primer") == ("primer-mcp" in servers)


def test_relative_claude_path_works(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(STUB).parent.parent)
    rel = str(Path(STUB).relative_to(Path.cwd()))
    code = run_eval.main(
        ["--batch", "pilot", "--scenario", SCENARIO, "--arm", "baseline"]
        + ["--claude", rel, "--runs-dir", str(tmp_path)]
    )
    assert code == 0


REAL_INIT = json.loads((Path(__file__).parent / "init_event_2.1.283.json").read_text())


def isolation(tmp_path, arm, event, user_home):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(event) + "\n")
    return run_eval.check_isolation(arm, transcript, user_home)


def fake_user_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "skills" / "portfolio-review").mkdir(parents=True)
    (home / ".claude" / "agents").mkdir()
    (home / ".claude" / "agents" / "search.md").write_text("x")
    return home


def test_real_init_event_passes_both_arms(tmp_path):
    home = fake_user_home(tmp_path)
    baseline = {
        **REAL_INIT,
        "mcp_servers": [],
        "tools": [t for t in REAL_INIT["tools"] if not t.startswith("mcp__")],
    }  # noqa: E501
    assert isolation(tmp_path, "primer", REAL_INIT, home) == []
    assert isolation(tmp_path, "baseline", baseline, home) == []


def test_user_skill_agent_plugin_or_memory_leaks_fail(tmp_path):
    home = fake_user_home(tmp_path)
    leaks = [
        {"skills": REAL_INIT["skills"] + ["portfolio-review"]},
        {"agents": REAL_INIT["agents"] + ["search"]},
        {"plugins": REAL_INIT["plugins"] + [{"name": "mine", "path": "/home/me/plugin"}]},
        {"memory_paths": {"auto": "/home/me/.claude/projects/x/memory/"}},
    ]
    for leak in leaks:
        assert isolation(tmp_path, "primer", {**REAL_INIT, **leak}, home), leak
