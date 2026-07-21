"""Opt-in live smoke test against the real Nexus cloud (read-only, free).

Run with a real account:  QNEXUS_MCP_LIVE=1 uv run pytest tests/smoke/ -v
(after `qnx login`). Never runs in CI. This is the checkpoint that verifies the QnexusClient
signatures marked VERIFY LIVE against the installed SDK.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("QNEXUS_MCP_LIVE") != "1",
    reason="set QNEXUS_MCP_LIVE=1 and run `qnx login` first",
)


def test_live_auth_and_devices():
    from qnexus_mcp.client import QnexusClient

    client = QnexusClient()
    status = client.auth_status()
    assert status["logged_in"] is True, "run `qnx login` first"

    devices = client.list_devices()
    assert devices, "expected at least one available device"
    assert any(str(d.get("name", "")).upper().endswith("LE") for d in devices), (
        "expected a free noiseless emulator (a *-1LE device) to be listed"
    )
