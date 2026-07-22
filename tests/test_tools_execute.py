import types

import anyio
import pytest
from fastmcp.exceptions import ToolError

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.context import bind_state
from qnexus_mcp.guards import SpendDenied
from qnexus_mcp.server import build_server
from qnexus_mcp.tools.execute import EXECUTE_SPECS, nexus_submit, nexus_submit_and_wait


class _Elicit:
    """Fake ctx.elicit returning an Accepted/Declined-shaped result."""

    def __init__(self, accept: bool = True, data: bool = True) -> None:
        self._accept = accept
        self._data = data

    async def __call__(self, message, response_type=bool):
        action = "accept" if self._accept else "decline"
        return types.SimpleNamespace(action=action, data=self._data)


def _ctx(client, config, elicit=None, progress_log=None):
    async def report_progress(progress, total=None, message=None):
        if progress_log is not None:
            progress_log.append((progress, total, message))

    server = types.SimpleNamespace()
    bind_state(server, client, config)
    return types.SimpleNamespace(
        fastmcp=server, elicit=elicit or _Elicit(), report_progress=report_progress
    )


async def test_submit_defaults_to_free_emulator_and_runs(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    out = await nexus_submit(_ctx(fake_client, cfg), circuit="OPENQASM 3;", n_shots=100)
    assert out["device"] == "H2-1LE"
    assert out["job_id"] == "j-new"


async def test_submit_billable_blocked_without_allow_spend(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    with pytest.raises(SpendDenied, match="allow-spend"):
        await nexus_submit(_ctx(fake_client, cfg), circuit="...", n_shots=100, device="H2-1E")


async def test_submit_billable_runs_with_flags_and_confirmation(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    ctx = _ctx(fake_client, cfg, _Elicit(accept=True, data=True))
    out = await nexus_submit(ctx, circuit="...", n_shots=100, device="H2-1E")
    assert out["device"] == "H2-1E"


async def test_submit_billable_denied_when_user_declines(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    ctx = _ctx(fake_client, cfg, _Elicit(accept=False))
    with pytest.raises(SpendDenied, match="not confirmed"):
        await nexus_submit(ctx, circuit="...", n_shots=100, device="H2-1E")


def test_execute_specs_shape():
    assert {s.name for s in EXECUTE_SPECS} == {
        "nexus_estimate_cost",
        "nexus_compile",
        "nexus_submit",
        "nexus_submit_and_wait",
    }
    assert all(s.toolset == "execute" and not s.read_only for s in EXECUTE_SPECS)


async def test_submit_and_wait_runs_on_free_emulator(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    out = await nexus_submit_and_wait(_ctx(fake_client, cfg), circuit="x", n_shots=10)
    assert out["counts"] == {"00": 51, "11": 49}
    assert out["omitted_outcomes"] == 0  # shaped through the same truncation path as get_results


async def test_submit_and_wait_reports_progress_during_poll(fake_client):
    class QueuedThenDoneClient:
        def __init__(self):
            self._polls = 0

        def __getattr__(self, item):
            return getattr(fake_client, item)

        def job_status(self, job_id):
            self._polls += 1
            if self._polls == 1:
                return {"id": job_id, "status": "QUEUED", "queue_position": 2}
            return {"id": job_id, "status": "COMPLETED"}

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    log = []
    ctx = _ctx(QueuedThenDoneClient(), cfg, progress_log=log)
    out = await nexus_submit_and_wait(ctx, circuit="x", n_shots=10, timeout=30)
    assert out["counts"] == {"00": 51, "11": 49}
    assert len(log) == 2
    assert "QUEUED" in log[0][2] and "2" in log[0][2]


async def test_submit_and_wait_surfaces_terminal_error_as_tool_error(fake_client):
    class ErroringClient:
        def __getattr__(self, item):
            return getattr(fake_client, item)

        def job_status(self, job_id):
            return {"id": job_id, "status": "ERROR", "message": "device rejected the circuit"}

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    with pytest.raises(ToolError, match="device rejected the circuit"):
        await nexus_submit_and_wait(_ctx(ErroringClient(), cfg), circuit="x", n_shots=10)


async def test_submit_hardware_needs_allow_hardware(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=100.0)
    with pytest.raises(SpendDenied, match="allow-hardware"):
        await nexus_submit(
            _ctx(fake_client, cfg, _Elicit(accept=True)),
            circuit="x",
            n_shots=10,
            device="H2-1",
        )


def test_billable_denial_message_survives_the_call_path(fake_client):
    # Through the REAL FastMCP call path (mask_error_details=True), the guard message must survive.
    server = build_server(ServerConfig(toolsets=frozenset({"read", "execute"})), fake_client)

    async def _call():
        return await server.call_tool(
            "nexus_submit", {"circuit": "x", "n_shots": 10, "device": "H2-1E"}
        )

    with pytest.raises(SpendDenied, match="allow-spend"):
        anyio.run(_call)
