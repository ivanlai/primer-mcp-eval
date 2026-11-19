"""Export scored eval runs as Inspect AI logs, one .eval file per arm, for `inspect view`.

Reads runs/<batch>/<scenario>/<arm>/r<n>/ (prompt.txt, transcript.jsonl, meta.json) and the
frozen scores in results/<batch>/runs.csv, and writes results/<batch>/inspect/<arm>.eval.
Nothing is rerun or rescored: each sample's scores are its row in runs.csv. The runs were not
made by Inspect; the logs only reuse its format and viewer.

Usage: uv sync   # once: dev environment with inspect_ai
       uv run python scripts/export_inspect.py --batch headline
       uv run inspect view --log-dir results/headline/inspect
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalMetric,
    EvalResults,
    EvalSample,
    EvalScore,
    EvalStats,
    EvalSpec,
    write_eval_log,
)
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ModelOutput,
)
from inspect_ai.scorer import Score
from inspect_ai.tool import ToolCall, ToolCallError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import RATE_METRICS, events, rate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NUMBERS = ["out_of_scope", "cost_usd", "turns", "duration_s", "primer_calls", "tickets_created"]


def parse(value: str):
    """A runs.csv cell as written by csv.DictWriter: True/False, blank for None, or a number."""
    if value in ("True", "False"):
        return value == "True"
    if value == "":
        return None
    return float(value)


def tool_text(content) -> str:
    """A tool result as text. ToolSearch returns tool_reference blocks: shown as tool names."""
    if not isinstance(content, list):
        return content or ""
    parts = []
    for b in content:
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
        elif b.get("type") == "tool_reference":
            parts.append(b.get("tool_name", ""))
        else:
            parts.append(json.dumps(b))
    return "\n".join(parts)


def messages(prompt: str, evs: list[dict], model: str) -> list:
    """Claude Code stream-json events as Inspect messages.

    Claude Code emits one assistant event per content block, sometimes with tool results in
    between, so all events with the same message id are merged into one assistant message.
    Thinking blocks are left out (headless runs record them empty).
    """
    out: list = [ChatMessageUser(content=prompt)]
    names: dict[str, str] = {}
    by_id: dict[str, ChatMessageAssistant] = {}
    for e in evs:
        if e.get("type") == "assistant":
            msg = e.get("message", {})
            current = by_id.get(msg.get("id"))
            if current is None:
                current = ChatMessageAssistant(content="", tool_calls=[], model=model)
                out.append(current)
                if msg.get("id") is not None:
                    by_id[msg["id"]] = current
            for block in msg.get("content", []) or []:
                if block.get("type") == "text":
                    current.content = (
                        current.content + "\n\n" + block["text"]
                        if current.content
                        else block["text"]
                    )
                elif block.get("type") == "tool_use":
                    names[block["id"]] = block["name"]
                    current.tool_calls.append(
                        ToolCall(id=block["id"], function=block["name"], arguments=block["input"])
                    )
        elif e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), list):
            for block in e["message"]["content"]:
                if block.get("type") != "tool_result":
                    continue
                text = tool_text(block.get("content"))
                out.append(
                    ChatMessageTool(
                        content=text,
                        tool_call_id=block["tool_use_id"],
                        function=names.get(block["tool_use_id"]),
                        error=ToolCallError("unknown", text) if block.get("is_error") else None,
                    )
                )
    return out


def sample(run_dir: Path, row: dict, model: str) -> EvalSample:
    evs = events(run_dir / "transcript.jsonl")
    times = [e["timestamp"] for e in evs if e.get("timestamp")]
    result = next((e for e in reversed(evs) if e.get("type") == "result"), {})
    prompt = (run_dir / "prompt.txt").read_text()
    scores = {m: Score(value="C" if row[m] else "I") for m in RATE_METRICS if row[m] is not None}
    return EvalSample(
        id=f"{row['scenario']}/{row['rep']}",
        epoch=1,
        input=prompt,
        target="",
        messages=messages(prompt, evs, model),
        output=ModelOutput.from_content(model, result.get("result", "") or ""),
        scores=scores,
        metadata={"kind": row["kind"], **{k: row[k] for k in NUMBERS}},
        total_time=row["duration_s"],
        started_at=min(times) if times else None,
        completed_at=max(times) if times else None,
    )


def arm_log(arm: str, batch: str, runs: list[tuple[Path, dict]]) -> EvalLog:
    meta = json.loads((runs[0][0] / "meta.json").read_text())
    model = meta["pins"]["model"]
    rows = [row for _, row in runs]
    samples = [sample(d, row, model) for d, row in runs]
    results = EvalResults(
        total_samples=len(samples),
        completed_samples=len(samples),
        scores=[
            EvalScore(
                name=m,
                scorer=m,
                metrics={"accuracy": EvalMetric(name="accuracy", value=rate(rows, m))},
            )
            for m in RATE_METRICS
            if rate(rows, m) is not None
        ],
    )
    return EvalLog(
        status="success",
        eval=EvalSpec(
            created=datetime.now(timezone.utc).isoformat(),
            task=f"primer-mcp-eval/{arm}",
            dataset=EvalDataset(
                name=batch, samples=len(samples), sample_ids=[s.id for s in samples]
            ),
            model=f"anthropic/{model}",
            config=EvalConfig(),
            metadata={
                "pins": meta["pins"],
                "limits": meta["limits"],
                "note": "Converted from headless Claude Code runs; scores from runs.csv.",
            },
        ),
        results=results,
        stats=EvalStats(
            started_at=min(s.started_at for s in samples if s.started_at),
            completed_at=max(s.completed_at for s in samples if s.completed_at),
        ),
        samples=samples,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export scored runs as Inspect logs.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=ROOT / "results")
    args = parser.parse_args(argv)

    with (args.results_dir / args.batch / "runs.csv").open() as f:
        rows = [{k: v if k in ("scenario", "kind", "arm", "rep") else parse(v)
                 for k, v in r.items()} for r in csv.DictReader(f)]  # fmt: skip
    by_arm: dict[str, list[tuple[Path, dict]]] = {}
    for row in rows:
        run_dir = args.runs_dir / args.batch / row["scenario"] / row["arm"] / row["rep"]
        if not run_dir.is_dir():
            sys.exit(f"no run directory for {row['scenario']}/{row['arm']}/{row['rep']}")
        by_arm.setdefault(row["arm"], []).append((run_dir, row))

    out = args.out / args.batch / "inspect"
    for arm, runs in sorted(by_arm.items()):
        write_eval_log(arm_log(arm, args.batch, runs), str(out / f"{arm}.eval"))
        print(f"{arm}: {len(runs)} samples -> {out / f'{arm}.eval'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
