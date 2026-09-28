"""Run eval scenarios as isolated headless Claude Code sessions (ADR-002, ADR-003, ADR-005).

Each run gets a fresh git repo of the fixture, a throwaway HOME (so no user-level
CLAUDE.md, memory, hooks, git config or MCP servers reach it), pinned versions from
eval.toml, and --strict-mcp-config. The primer arm has init_project applied before
the initial commit; the baseline arm has no MCP servers at all.

Output, per run: runs/<batch>/<scenario>/<arm>/r<n>/ with prompt.txt, command.json,
transcript.jsonl, stderr.txt, meta.json and repo/ (the final working copy). A run
whose meta.json exists is skipped, so an interrupted batch can be resumed.

Usage:
  python3 scripts/run_eval.py --batch pilot [--scenario ID ...] [--arm baseline|primer ...]
                              [--reps N] [--dry-run] [--claude PATH]

Real runs need ANTHROPIC_API_KEY: the isolated HOME has no stored login.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "scenarios"
RUNS = ROOT / "runs"
FIXTURE = "fixtures/app"
ARMS = ("baseline", "primer")
BATCHES = ("pilot", "headline")
PROJECT_NAME = "expenses"


def load_config() -> dict:
    return tomllib.loads((ROOT / "eval.toml").read_text())


def compose_prompt(scenario: str) -> str:
    request = (SCENARIOS / scenario / "prompt.md").read_text().strip()
    autonomy = (SCENARIOS / "autonomy.txt").read_text().strip()
    return f"{request}\n\n{autonomy}\n"


def mcp_config(arm: str, primer_version: str, uvx: str) -> dict:
    if arm == "baseline":
        return {"mcpServers": {}}
    return {
        "mcpServers": {
            "primer-mcp": {"command": uvx, "args": [f"primer-mcp=={primer_version}", "serve"]}
        }
    }


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=git_env())


def git_env() -> dict:
    """Git without the developer's global config or hooks."""
    return {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def prepare_repo(repo: Path, arm: str, primer_version: str) -> None:
    """Fresh fixture from git HEAD as a new repo with one neutral commit."""
    repo.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", f"HEAD:{FIXTURE}"], cwd=ROOT, check=True, capture_output=True
    )
    subprocess.run(["tar", "-x", "-C", str(repo)], input=archive.stdout, check=True)
    if arm == "primer":
        code = (
            "import sys; from pathlib import Path; from primer_mcp.project import init_project;"
            f" init_project(Path(sys.argv[1]), {PROJECT_NAME!r})"
        )
        subprocess.run(
            ["uvx", "-q", "--from", f"primer-mcp=={primer_version}", "python", "-c", code, repo],
            check=True,
            capture_output=True,
        )
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Developer")
    git(repo, "config", "user.email", "developer@example.com")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Initial commit")


def claude_command(claude: str, cfg: dict, mcp_file: Path) -> list[str]:
    pins, limits = cfg["pins"], cfg["limits"]
    return [
        claude,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        pins["model"],
        "--max-budget-usd",
        str(limits["budget_usd"]),
        "--permission-mode",
        limits["permission_mode"],
        "--mcp-config",
        str(mcp_file),
        "--strict-mcp-config",
        "--no-session-persistence",
    ]


def run_env(home: Path) -> dict:
    """Real PATH and package caches, but an empty HOME and no inherited Claude settings."""
    keep = ("PATH", "LANG", "LC_ALL", "TERM", "ANTHROPIC_API_KEY", "TMPDIR")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["UV_CACHE_DIR"] = os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv"))
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def init_event(transcript: Path) -> dict | None:
    if not transcript.is_file():
        return None
    for line in transcript.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            return event
    return None


def check_isolation(arm: str, transcript: Path) -> list[str]:
    """Problems with what the session loaded, from its init event; empty means isolated."""
    event = init_event(transcript)
    if event is None:
        return ["no init event in the transcript"]
    servers = {s.get("name") for s in event.get("mcp_servers", [])}
    mcp_tools = [t for t in event.get("tools", []) if t.startswith("mcp__")]
    problems = []
    if arm == "baseline":
        if servers or mcp_tools:
            problems.append(f"baseline loaded MCP servers {sorted(servers)} / tools {mcp_tools}")
    else:
        if servers != {"primer-mcp"}:
            problems.append(f"primer arm expected only primer-mcp, got {sorted(servers)}")
        if not any(t.startswith("mcp__primer-mcp__") for t in mcp_tools):
            problems.append("primer arm has no primer-mcp tools")
    return problems


def run_one(run_dir: Path, scenario: str, arm: str, cfg: dict, claude: str, dry_run: bool) -> dict:
    prompt = compose_prompt(scenario)
    with tempfile.TemporaryDirectory(prefix="eval-home-") as tmp:
        home = Path(tmp)
        mcp_file = home / "mcp.json"
        uvx = shutil.which("uvx") or "uvx"
        mcp_file.write_text(json.dumps(mcp_config(arm, cfg["pins"]["primer_mcp"], uvx), indent=2))
        cmd = claude_command(claude, cfg, mcp_file)
        env = run_env(home)
        if dry_run:
            print(f"--- {run_dir}")
            print("command:", " ".join(cmd))
            print("env:", {k: ("<set>" if "KEY" in k else v) for k, v in env.items()})
            print("mcp:", mcp_file.read_text().strip())
            print("prompt:", prompt)
            return {"dry_run": True}

        run_dir.mkdir(parents=True, exist_ok=True)
        repo = run_dir / "repo"
        prepare_repo(repo, arm, cfg["pins"]["primer_mcp"])
        (run_dir / "prompt.txt").write_text(prompt)
        (run_dir / "command.json").write_text(
            json.dumps({"argv": cmd, "mcp": json.loads(mcp_file.read_text())}, indent=2)
        )
        transcript = run_dir / "transcript.jsonl"
        start = time.monotonic()
        with transcript.open("w") as out, (run_dir / "stderr.txt").open("w") as err:
            try:
                proc = subprocess.run(
                    cmd,
                    input=prompt,
                    cwd=repo,
                    env=env,
                    stdout=out,
                    stderr=err,
                    text=True,
                    timeout=cfg["limits"]["timeout_s"],
                )
                exit_code, timed_out = proc.returncode, False
            except subprocess.TimeoutExpired:
                exit_code, timed_out = None, True
        meta = {
            "scenario": scenario,
            "arm": arm,
            "pins": cfg["pins"],
            "limits": cfg["limits"],
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_s": round(time.monotonic() - start, 1),
            "isolation_problems": check_isolation(arm, transcript),
        }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def check_cli_version(claude: str, expected: str) -> None:
    out = subprocess.run([claude, "--version"], capture_output=True, text=True).stdout
    if not out.startswith(expected):
        sys.exit(f"claude --version is {out.strip()!r}; eval.toml pins {expected}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run eval scenarios headless.")
    parser.add_argument("--batch", choices=BATCHES, required=True)
    parser.add_argument("--scenario", action="append", help="scenario id (default: all)")
    parser.add_argument("--arm", action="append", choices=ARMS, help="arm (default: both)")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="print, don't run")
    parser.add_argument("--claude", help="claude binary (default: from PATH; tests use a stub)")
    parser.add_argument("--runs-dir", type=Path, default=RUNS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    cfg = load_config()
    claude = args.claude or shutil.which("claude")
    if not claude:
        sys.exit("claude not found on PATH")
    if not args.claude:
        check_cli_version(claude, cfg["pins"]["claude_cli"])
        if not args.dry_run and "ANTHROPIC_API_KEY" not in os.environ:
            sys.exit("ANTHROPIC_API_KEY is not set; the isolated HOME has no stored login")

    scenarios = args.scenario or sorted(p.parent.name for p in SCENARIOS.glob("*/scenario.toml"))
    arms = args.arm or list(ARMS)
    failures = 0
    for scenario in scenarios:
        for arm in arms:
            for rep in range(1, args.reps + 1):
                run_dir = args.runs_dir / args.batch / scenario / arm / f"r{rep}"
                if (run_dir / "meta.json").exists():
                    print(f"skip  {run_dir.relative_to(args.runs_dir)} (already done)")
                    continue
                meta = run_one(run_dir, scenario, arm, cfg, claude, args.dry_run)
                if args.dry_run:
                    continue
                bad = meta["isolation_problems"] or meta["exit_code"] != 0
                failures += bool(bad)
                status = "FAIL" if bad else "ok  "
                print(f"{status}  {run_dir.relative_to(args.runs_dir)}  {meta['duration_s']}s")
                for problem in meta["isolation_problems"]:
                    print(f"        {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
