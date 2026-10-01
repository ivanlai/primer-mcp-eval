"""Run eval scenarios as isolated headless Claude Code sessions (ADR-002, ADR-003, ADR-005).

Each run gets a fresh git repo of the fixture, a throwaway HOME (so no user-level
CLAUDE.md, memory, hooks, git config or MCP servers reach it), pinned versions from
eval.toml, and --strict-mcp-config. The primer arm has init_project applied before
the initial commit; the baseline arm has no MCP servers at all; the instructions arm
(ADR-006) is the baseline plus a CLAUDE.md that says only "Plan first."

Output, per run: runs/<batch>/<scenario>/<arm>/r<n>/ with prompt.txt, command.json,
transcript.jsonl, stderr.txt, meta.json and repo/ (the final working copy). A run
whose meta.json exists is skipped, so an interrupted batch can be resumed.

Usage:
  python3 scripts/run_eval.py --batch pilot [--scenario ID ...] [--arm baseline|primer|instructions ...]
                              [--reps N] [--dry-run] [--claude PATH]

Real runs need credentials passed in explicitly, because the isolated HOME has no stored
login: CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`, which uses a Claude subscription)
in the environment or in ~/.config/primer-mcp-eval/oauth-token, or ANTHROPIC_API_KEY.
--redo-failed reruns runs that failed or failed the isolation check. --wait-on-limit makes
an unattended batch ride out usage limits: a failed run is deleted, the runner waits (15
minutes, doubling to an hour) and retries it, and stops after 4 retries of one run or
8 hours of waiting in total.
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
ARMS = ("baseline", "primer", "instructions")
INSTRUCTIONS = "Plan first.\n"  # the instructions arm's whole CLAUDE.md
BATCHES = ("pilot", "headline")
PROJECT_NAME = "expenses"
RETRY_WAITS_S = (900, 1800, 3600, 3600)  # per failed run, then give up on the batch
MAX_TOTAL_WAIT_S = 8 * 3600
SLEEP = time.sleep  # replaced in tests
TOKEN_FILE = Path.home() / ".config" / "primer-mcp-eval" / "oauth-token"
CLAUDE_VERSIONS = Path.home() / ".local" / "share" / "claude" / "versions"


def load_config() -> dict:
    return tomllib.loads((ROOT / "eval.toml").read_text())


def compose_prompt(scenario: str) -> str:
    request = (SCENARIOS / scenario / "prompt.md").read_text().strip()
    autonomy = (SCENARIOS / "autonomy.txt").read_text().strip()
    return f"{request}\n\n{autonomy}\n"


def mcp_config(arm: str, primer_version: str, uvx: str) -> dict:
    if arm != "primer":
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
    elif arm == "instructions":
        (repo / "CLAUDE.md").write_text(INSTRUCTIONS)
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


def credentials() -> dict:
    """The one credential passed to runs: a subscription token, else an API key."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token and TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text().strip()
    if token:
        return {"CLAUDE_CODE_OAUTH_TOKEN": token}
    if os.environ.get("ANTHROPIC_API_KEY"):
        return {"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]}
    return {}


def run_env(home: Path) -> dict:
    """Real PATH and package caches, but an empty HOME and no inherited Claude settings."""
    keep = ("PATH", "LANG", "LC_ALL", "TERM", "TMPDIR")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(credentials())
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["UV_CACHE_DIR"] = os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv"))
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"
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


def user_config_names(home: Path) -> tuple[set[str], set[str]]:
    """Names of the developer's own skills and agents, which must never reach a run."""
    skills_dir, agents_dir = home / ".claude" / "skills", home / ".claude" / "agents"
    skills = {p.name for p in skills_dir.iterdir()} if skills_dir.is_dir() else set()
    agents = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.is_dir() else set()
    return skills, agents


def run_failed(exit_code: int | None, transcript: Path) -> bool:
    """The session itself failed (limit, auth, crash), as opposed to the agent's work."""
    if exit_code != 0:
        return True
    evs = [json.loads(line) for line in transcript.read_text().splitlines() if line.strip()]
    result = next((e for e in reversed(evs) if e.get("type") == "result"), None)
    return result is None or bool(result.get("is_error")) or any("error" in e for e in evs)


def check_isolation(arm: str, transcript: Path, user_home: Path | None = None) -> list[str]:
    """Problems with what the session loaded, from its init event; empty means isolated."""
    event = init_event(transcript)
    if event is None:
        return ["no init event in the transcript"]
    user_skills, user_agents = user_config_names(user_home or Path.home())
    problems = []
    leaked = sorted(set(event.get("skills", [])) & user_skills)
    leaked += sorted(set(event.get("agents", [])) & user_agents)
    if leaked:
        problems.append(f"user-level skills or agents loaded: {leaked}")
    plugins = [p.get("name") for p in event.get("plugins", []) if p.get("path") != "builtin"]
    if plugins:
        problems.append(f"non-built-in plugins loaded: {plugins}")
    memory = [m for m in (event.get("memory_paths") or {}).values() if "eval-home-" not in m]
    if memory:
        problems.append(f"memory outside the run's HOME: {memory}")
    cwd = Path(event.get("cwd", "/"))
    if cwd == ROOT or ROOT in cwd.parents:
        problems.append(f"session ran inside the eval repo: {cwd}")
    if str(ROOT) in transcript.read_text():
        problems.append("the session referenced the eval repo's path")
    servers = {s.get("name") for s in event.get("mcp_servers", [])}
    mcp_tools = [t for t in event.get("tools", []) if t.startswith("mcp__")]
    if arm == "primer":
        if servers != {"primer-mcp"}:
            problems.append(f"primer arm expected only primer-mcp, got {sorted(servers)}")
        if not any(t.startswith("mcp__primer-mcp__") for t in mcp_tools):
            problems.append("primer arm has no primer-mcp tools")
    elif servers or mcp_tools:
        problems.append(f"{arm} loaded MCP servers {sorted(servers)} / tools {mcp_tools}")
    return problems


def run_one(run_dir: Path, scenario: str, arm: str, cfg: dict, claude: str, dry_run: bool) -> dict:
    prompt = compose_prompt(scenario)
    # HOME and the working repo both live outside the eval repo: Claude Code reads CLAUDE.md
    # from parent directories, and an agent searching upwards must not find scenarios/.
    with (
        tempfile.TemporaryDirectory(prefix="eval-home-") as tmp,
        tempfile.TemporaryDirectory(prefix="eval-work-") as work_tmp,
    ):
        home = Path(tmp)
        mcp_file = home / "mcp.json"
        uvx = shutil.which("uvx") or "uvx"
        mcp_file.write_text(json.dumps(mcp_config(arm, cfg["pins"]["primer_mcp"], uvx), indent=2))
        cmd = claude_command(claude, cfg, mcp_file)
        env = run_env(home)
        if dry_run:
            print(f"--- {run_dir}")
            print("command:", " ".join(cmd))
            secret = ("KEY", "TOKEN")
            print(
                "env:", {k: ("<set>" if any(s in k for s in secret) else v) for k, v in env.items()}
            )
            print("mcp:", mcp_file.read_text().strip())
            print("prompt:", prompt)
            return {"dry_run": True}

        run_dir.mkdir(parents=True, exist_ok=True)
        repo = Path(work_tmp) / "repo"
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
            "run_failed": timed_out or run_failed(exit_code, transcript),
        }
        shutil.copytree(
            repo, run_dir / "repo", symlinks=True, ignore=shutil.ignore_patterns(".venv")
        )
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
    parser.add_argument("--arm", action="append", choices=ARMS, help="arm (default: all)")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="print, don't run")
    parser.add_argument("--redo-failed", action="store_true", help="rerun failed runs")
    parser.add_argument(
        "--wait-on-limit", action="store_true", help="wait and retry failed runs (overnight)"
    )
    parser.add_argument("--claude", help="claude binary (default: from PATH; tests use a stub)")
    parser.add_argument("--runs-dir", type=Path, default=RUNS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    cfg = load_config()
    # The pinned version's own binary, so an auto-update of `claude` can't change a batch.
    pinned = CLAUDE_VERSIONS / cfg["pins"]["claude_cli"]
    claude = str(Path(args.claude).resolve()) if args.claude else str(pinned)
    if not args.claude and not pinned.is_file():
        sys.exit(f"pinned claude {pinned} is not installed")
    if not args.claude:
        check_cli_version(claude, cfg["pins"]["claude_cli"])
        if not args.dry_run and not credentials():
            sys.exit(
                "no credentials: run `claude setup-token` and put the token in "
                f"{TOKEN_FILE} (or set CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY)"
            )

    scenarios = args.scenario or sorted(p.parent.name for p in SCENARIOS.glob("*/scenario.toml"))
    arms = args.arm or list(ARMS)
    failures, waited = 0, 0
    for scenario in scenarios:
        for arm in arms:
            for rep in range(1, args.reps + 1):
                run_dir = args.runs_dir / args.batch / scenario / arm / f"r{rep}"
                if (run_dir / "meta.json").exists():
                    done = json.loads((run_dir / "meta.json").read_text())
                    failed = done.get("run_failed", done["exit_code"] != 0)
                    failed = failed or done["isolation_problems"]
                    if not (args.redo_failed and failed):
                        print(f"skip  {run_dir.relative_to(args.runs_dir)} (already done)")
                        continue
                    shutil.rmtree(run_dir)
                meta = run_one(run_dir, scenario, arm, cfg, claude, args.dry_run)
                if args.dry_run:
                    continue
                for wait in RETRY_WAITS_S if args.wait_on_limit else ():
                    if not meta["run_failed"] or waited + wait > MAX_TOTAL_WAIT_S:
                        break
                    print(f"wait  {run_dir.relative_to(args.runs_dir)} failed; retry in {wait}s")
                    shutil.rmtree(run_dir)
                    SLEEP(wait)
                    waited += wait
                    meta = run_one(run_dir, scenario, arm, cfg, claude, args.dry_run)
                if args.wait_on_limit and meta["run_failed"]:
                    print(f"FAIL  {run_dir.relative_to(args.runs_dir)}: still failing, stopping")
                    return 1
                bad = meta["isolation_problems"] or meta["run_failed"]
                failures += bool(bad)
                status = "FAIL" if bad else "ok  "
                print(f"{status}  {run_dir.relative_to(args.runs_dir)}  {meta['duration_s']}s")
                for problem in meta["isolation_problems"]:
                    print(f"        {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
