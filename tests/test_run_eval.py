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


def test_every_arm_produces_full_layout(tmp_path):
    assert run(tmp_path) == 0
    for arm in run_eval.ARMS:
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


def test_instructions_arm_has_only_the_one_line_claude_md(tmp_path):
    run(tmp_path, "--arm", "instructions")
    d = tmp_path / "pilot" / SCENARIO / "instructions" / "r1"
    assert (
        d / "repo" / "CLAUDE.md"
    ).read_text() == "Plan first, and save the plan in docs/ before changing code.\n"
    assert not (d / "repo" / "primer").exists() and not (d / "repo" / "AGENTS.md").exists()
    tracked = subprocess.run(["git", "ls-files"], cwd=d / "repo", capture_output=True, text=True)
    assert "CLAUDE.md" in tracked.stdout.split()
    assert json.loads((d / "command.json").read_text())["mcp"] == {"mcpServers": {}}


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


@pytest.mark.parametrize("arm", run_eval.ARMS)
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
    assert isolation(tmp_path, "instructions", baseline, home) == []


def test_instructions_arm_with_primer_mcp_fails_isolation(tmp_path):
    problems = isolation(tmp_path, "instructions", REAL_INIT, fake_user_home(tmp_path))
    assert any("instructions loaded MCP servers" in p for p in problems)


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


def test_redo_failed_reruns_only_failed_runs(tmp_path):
    run(tmp_path, "--arm", "baseline")
    meta_file = tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "meta.json"
    meta = json.loads(meta_file.read_text())
    meta["exit_code"], meta["run_failed"] = 1, True
    meta_file.write_text(json.dumps(meta))
    run(tmp_path, "--arm", "baseline")  # without the flag: skipped, still failed
    assert json.loads(meta_file.read_text())["exit_code"] == 1
    run(tmp_path, "--arm", "baseline", "--redo-failed")
    assert json.loads(meta_file.read_text())["exit_code"] == 0


def test_subscription_token_is_passed_and_nothing_else(monkeypatch, tmp_path):
    monkeypatch.setattr(run_eval, "TOKEN_FILE", tmp_path / "oauth-token")
    (tmp_path / "oauth-token").write_text("tok-123\n")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-456")
    env = run_eval.run_env(tmp_path / "home")
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-123"
    assert "ANTHROPIC_API_KEY" not in env


def test_session_runs_outside_the_eval_repo(tmp_path):
    run(tmp_path, "--arm", "baseline")
    transcript = tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "transcript.jsonl"
    cwd = Path(json.loads(transcript.read_text().splitlines()[0])["cwd"])
    assert run_eval.ROOT not in cwd.parents
    assert (tmp_path / "pilot" / SCENARIO / "baseline" / "r1" / "repo" / "stub_note.txt").is_file()


def test_eval_repo_cwd_or_path_in_transcript_fails(tmp_path):
    home = fake_user_home(tmp_path)
    inside = {**REAL_INIT, "cwd": str(run_eval.ROOT / "runs" / "x" / "repo")}
    assert any("inside the eval repo" in p for p in isolation(tmp_path, "primer", inside, home))
    transcript = tmp_path / "t2.jsonl"
    grep = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {"command": f"grep -r x {run_eval.ROOT}"},
                }
            ]
        },
    }
    transcript.write_text(json.dumps(REAL_INIT) + "\n" + json.dumps(grep) + "\n")
    problems = run_eval.check_isolation("primer", transcript, home)
    assert any("referenced the eval repo" in p for p in problems)


def flaky_claude(tmp_path, failures):
    """A stub that fails like a usage limit for its first `failures` calls, then works."""
    count = tmp_path / "calls"
    script = tmp_path / "flaky_claude"
    script.write_text(
        "#!/bin/sh\n"
        f"n=$(cat {count} 2>/dev/null || echo 0); echo $((n+1)) > {count}\n"
        f'if [ "$n" -lt {failures} ]; then\n'
        '  echo \'{"type":"system","subtype":"init","tools":[],"mcp_servers":[]}\'\n'
        '  echo \'{"type":"assistant","error":"rate_limit","message":{"content":[]}}\'\n'
        '  echo \'{"type":"result","is_error":true,"result":"Usage limit reached"}\'\n'
        "  exit 1\nfi\n"
        f'exec {STUB} "$@"\n'
    )
    script.chmod(0o755)
    return str(script)


def run_waiting(tmp_path, claude, monkeypatch):
    slept = []
    monkeypatch.setattr(run_eval, "SLEEP", slept.append)
    code = run_eval.main(
        ["--batch", "pilot", "--scenario", SCENARIO, "--arm", "baseline", "--wait-on-limit"]
        + ["--claude", claude, "--runs-dir", str(tmp_path / "runs")]
    )
    return code, slept


def test_wait_on_limit_retries_until_the_run_succeeds(tmp_path, monkeypatch):
    code, slept = run_waiting(tmp_path, flaky_claude(tmp_path, 2), monkeypatch)
    assert code == 0 and slept == [900, 1800]
    meta = tmp_path / "runs" / "pilot" / SCENARIO / "baseline" / "r1" / "meta.json"
    assert json.loads(meta.read_text())["run_failed"] is False


def test_wait_on_limit_gives_up_after_the_retry_cap(tmp_path, monkeypatch):
    code, slept = run_waiting(tmp_path, flaky_claude(tmp_path, 99), monkeypatch)
    assert code == 1 and slept == list(run_eval.RETRY_WAITS_S)


def test_zero_exit_with_an_error_result_counts_as_failed(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"type":"result","is_error":true,"result":"Usage limit reached"}\n')
    assert run_eval.run_failed(0, transcript) is True
    transcript.write_text('{"type":"result","is_error":false,"result":"Done."}\n')
    assert run_eval.run_failed(0, transcript) is False
