"""Snapshot of the full agent-facing tool catalog (DESIGN §12).

Names, descriptions, annotations, and input/output schemas are what the LLM sees; they must never
drift silently. If a change is intentional, regenerate with:

    UPDATE_SNAPSHOTS=1 uv run pytest tests/test_toolsnap.py && git diff tests/snapshots/
"""

import json
import os
from pathlib import Path

import anyio

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.server import build_server

SNAPSHOT = Path(__file__).parent / "snapshots" / "tool_catalog.json"


def _catalog(fake_client) -> list[dict]:
    cfg = ServerConfig(
        toolsets=frozenset({"read", "execute", "manage", "destructive"}),
        allow_destructive=True,
    )
    server = build_server(cfg, fake_client)
    tools = anyio.run(server.list_tools)
    dumped = [
        t.to_mcp_tool().model_dump(exclude_none=True, exclude={"meta"}) for t in tools
    ]
    return sorted(dumped, key=lambda d: d["name"])


def test_tool_catalog_matches_snapshot(fake_client):
    catalog = _catalog(fake_client)
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    assert SNAPSHOT.exists(), "snapshot missing — run once with UPDATE_SNAPSHOTS=1"
    assert catalog == json.loads(SNAPSHOT.read_text()), (
        "the agent-facing tool catalog changed; if intentional, regenerate the snapshot "
        "(UPDATE_SNAPSHOTS=1) and review the diff"
    )
