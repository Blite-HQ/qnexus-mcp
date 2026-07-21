import types

import anyio
import pytest

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


def _ctx(client, config, elicit=None):
    server = types.SimpleNamespace()
    bind_state(server, client, config)
    return types.SimpleNamespace(fastmcp=server, elicit=elicit or _Elicit())


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
