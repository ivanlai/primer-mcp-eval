"""Validate the eval tasks in tasks/ against a fresh copy of the fixture.

For each task: its files are present and well formed, the prompt avoids words that
would hint at the workflow being measured, the check fails on the fixture as shipped,
and with reference.patch applied the check and the fixture's own suite pass and the
patch stays within expected_files (tests/ is always allowed). See tasks/README.md.

The fixture is exported from git HEAD, as the runner will do, so commit fixture
changes before validating against them.

Usage: python3 scripts/validate_tasks.py [task-id ...]
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
FIXTURE = "fixtures/app"
KINDS = {"feature", "bug", "refactor", "trivial", "ambiguous"}
BANNED = re.compile(
    r"\b(primer|tickets?|plan|plans|planning|adrs?|epics?|commits?|tests?|testing)\b",
    re.IGNORECASE,
)
VERB = {"failed": "fails", "error": "errors"}
PYTEST = ["uv", "run", "--quiet", "pytest", "-q", "-p", "no:cacheprovider"]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def task_dirs(ids: list[str]) -> list[Path]:
    if ids:
        return [TASKS / i for i in ids]
    return sorted(p.parent for p in TASKS.glob("*/task.toml"))


def fresh_fixture(dest: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", f"HEAD:{FIXTURE}"], cwd=ROOT, check=True, capture_output=True
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


def pytest(cwd: Path, *args: str) -> str:
    """Run pytest; return "passed", "failed" (assertions only) or "error"."""
    report = cwd / ".junit.xml"
    code = subprocess.run(
        [*PYTEST, f"--junitxml={report}", *args], cwd=cwd, env=ENV, capture_output=True
    ).returncode
    if code == 0:
        return "passed"
    if code == 1 and report.is_file():
        suite = ET.parse(report).getroot().find("testsuite")
        if suite is not None and int(suite.get("errors", 0)) == 0:
            return "failed"
    return "error"


def patched_files(patch: str) -> set[str]:
    return set(re.findall(r"^diff --git a/\S+ b/(\S+)$", patch, re.MULTILINE))


def validate(task: Path) -> list[str]:
    """Return the problems found with one task; empty means valid."""
    if not (task / "task.toml").is_file():
        return ["no task.toml"]
    problems = []

    meta = tomllib.loads((task / "task.toml").read_text())
    if meta.get("kind") not in KINDS:
        problems.append(f"kind must be one of {sorted(KINDS)}")
    expected = meta.get("expected_files")
    if not isinstance(expected, list) or not expected:
        problems.append("expected_files must be a non-empty list")
        expected = []

    prompt_file = task / "prompt.md"
    prompt = prompt_file.read_text().strip() if prompt_file.is_file() else ""
    if not prompt:
        problems.append("prompt.md missing or empty")
    for word in sorted({m.group(0).lower() for m in BANNED.finditer(prompt)}):
        problems.append(f"prompt mentions {word!r}")

    checks = list(task.glob("test_*.py"))
    patch_file = task / "reference.patch"
    if len(checks) != 1 or not patch_file.is_file():
        if len(checks) != 1:
            problems.append(f"expected one test_*.py check, found {len(checks)}")
        if not patch_file.is_file():
            problems.append("reference.patch missing")
        return problems

    patch = patch_file.read_text()
    outside = sorted(
        f
        for f in patched_files(patch)
        if not f.startswith("tests/") and not any(fnmatch.fnmatch(f, g) for g in expected)
    )
    if outside:
        problems.append(f"reference changes files outside expected_files: {outside}")

    check = ["--confcutdir", str(TASKS), str(checks[0])]
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        fresh_fixture(copy)
        before = pytest(copy, *check)
        if before == "passed":
            problems.append("check passes on the fixture as shipped")
        elif before == "error":
            problems.append("check errors (rather than fails) on the fixture as shipped")

        applied = subprocess.run(
            ["git", "apply", str(patch_file)], cwd=copy, capture_output=True, text=True
        )
        if applied.returncode != 0:
            return [*problems, f"reference.patch does not apply: {applied.stderr.strip()}"]
        after = pytest(copy, *check)
        if after != "passed":
            problems.append(f"check {VERB[after]} with the reference applied")
        suite = pytest(copy)
        if suite != "passed":
            problems.append(f"fixture suite {VERB[suite]} with the reference applied")
    return problems


def main(argv: list[str]) -> int:
    if not (TASKS / "autonomy.txt").is_file() or not (TASKS / "autonomy.txt").read_text().strip():
        print("tasks/autonomy.txt missing or empty")
        return 1
    tasks = task_dirs(argv)
    failed = 0
    for task in tasks:
        problems = validate(task)
        print(f"{'FAIL' if problems else 'ok  '}  {task.name}")
        for problem in problems:
            print(f"        {problem}")
        failed += bool(problems)
    print(f"\n{len(tasks) - failed}/{len(tasks)} tasks valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
