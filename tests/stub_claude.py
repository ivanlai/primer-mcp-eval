#!/usr/bin/env python3
"""Stand-in for `claude -p --output-format stream-json`, for offline runner tests.

Emits an init event listing the MCP servers from --mcp-config (or primer-mcp regardless,
when STUB_LEAKY=1), makes one file edit in the working directory, and ends with a result.
"""

import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if "--version" in args:
    print("2.1.283 (Claude Code)")
    sys.exit(0)
servers = json.loads(Path(args[args.index("--mcp-config") + 1]).read_text())["mcpServers"]
names = sorted(servers) or (["primer-mcp"] if os.environ.get("STUB_LEAKY") else [])
if os.environ.get("STUB_LEAKY"):
    names = sorted(set(names) | {"primer-mcp"})
tools = ["Bash", "Edit", "Read", "TodoWrite", "Write"]
tools += [f"mcp__{n}__plan_epic" for n in names]
prompt = sys.stdin.read()


def emit(event):
    print(json.dumps(event), flush=True)


emit(
    {
        "type": "system",
        "subtype": "init",
        "tools": tools,
        "mcp_servers": [{"name": n, "status": "connected"} for n in names],
        "home": os.environ["HOME"],
    }
)
Path("stub_note.txt").write_text(prompt)
emit(
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "stub_note.txt"}}
            ]
        },
    }
)
emit({"type": "result", "subtype": "success", "num_turns": 1, "total_cost_usd": 0.01})
