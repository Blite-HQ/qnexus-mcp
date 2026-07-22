"""Opt-in live smoke test against the real Nexus cloud (read-only, free).

Run with a real account:  QNEXUS_MCP_LIVE=1 uv run pytest tests/smoke/ -v
(after `qnx login`). Never runs in CI. This is the checkpoint that verifies the QnexusClient
read/execute signatures against the installed SDK and live Nexus.
"""

import os
import time

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
    names = [str(d.get("device_name") or "") for d in devices]
    assert any(n.upper().endswith("LE") for n in names), (
        f"expected a free noiseless emulator (a *-1LE device); saw {names}"
    )


def test_live_submit_free_emulator_bell():
    """End-to-end: compile + run a Bell circuit on the free H2-1LE emulator (0 HQC)."""
    from qnexus_mcp.client import QnexusClient

    qasm = (
        'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
        "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"
    )
    client = QnexusClient()
    job = client.submit(circuit=qasm, n_shots=20, device="H2-1LE")
    assert job["device"] == "H2-1LE" and job["job_id"]

    # Same primitive the nexus_submit_and_wait poll loop uses: cheap status GETs until done.
    deadline = time.monotonic() + 180
    while True:
        status = client.job_status(job["job_id"])["status"]
        if status == "COMPLETED":
            break
        assert time.monotonic() < deadline, f"job still {status} after 180s"
        time.sleep(5)

    results = client.get_results(job["job_id"])
    counts = results["counts_list"][0]
    assert sum(counts.values()) == 20
    assert set(counts) <= {"00", "11"}, f"expected only Bell outcomes, saw {counts}"
