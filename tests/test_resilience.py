"""Resilience + new-guard coverage: thread offload, error translation, rate limit, allowlist."""

import asyncio
import types

import pytest
from fastmcp.exceptions import ToolError

from qnexus_mcp.client import QnexusClient, _tool_error
from qnexus_mcp.config import ServerConfig
from qnexus_mcp.context import bind_state
from qnexus_mcp.guards import (
    ProjectDenied,
    RateLimited,
    SpendDenied,
    SpendGuard,
    SubmitRateLimiter,
    check_project_allowed,
)
from qnexus_mcp.tools.execute import nexus_submit, nexus_submit_and_wait
from qnexus_mcp.tools.manage import nexus_create_project
from qnexus_mcp.tools.read import nexus_device_status


class _Elicit:
    def __init__(self, accept: bool = True) -> None:
        self._accept = accept

    async def __call__(self, message, response_type=bool):
        return types.SimpleNamespace(
            action="accept" if self._accept else "decline", data=self._accept
        )


def _ctx(client, config=None, elicit=None):
    async def report_progress(progress, total=None, message=None):
        return None

    server = types.SimpleNamespace()
    bind_state(server, client, config or ServerConfig())
    return types.SimpleNamespace(
        fastmcp=server, elicit=elicit or _Elicit(), report_progress=report_progress
    )


# --- thread offload: the SDK's own asyncio.run must work from async tool handlers -------------


async def test_sdk_asyncio_run_works_via_tool(fake_client):
    """Parts of the qnexus SDK call asyncio.run() internally; called on the event loop that
    would RuntimeError. The tool path must offload every client call to a thread (regression
    for the M2 wiring, now exercised through the poll loop's job_status calls)."""

    class SdkLikeClient:
        def __getattr__(self, item):
            return getattr(fake_client, item)

        def job_status(self, job_id):
            async def sdk_internal():
                return {"id": job_id, "status": "COMPLETED"}

            return asyncio.run(sdk_internal())  # what e.g. qnx.jobs.wait_for does internally

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    out = await nexus_submit_and_wait(_ctx(SdkLikeClient(), cfg), circuit="OPENQASM 2.0;")
    assert out["counts"] == {"00": 51, "11": 49}


# --- error translation (QnexusClient._mapped / _tool_error) -----------------------------------


def test_auth_error_maps_to_qnx_login_guidance():
    import qnexus.exceptions as qnx_exc

    err = _tool_error(qnx_exc.AuthenticationError("boom"))
    assert isinstance(err, ToolError) and "qnx login" in str(err)


def test_server_5xx_maps_to_nexus_side_message_without_retry_loop_bait():
    import qnexus.exceptions as qnx_exc

    err = _tool_error(qnx_exc.ResourceFetchFailed(message="upstream", status_code=500))
    assert isinstance(err, ToolError)
    assert "Nexus-side" in str(err) and "do not retry in a loop" in str(err)


def test_ambiguous_match_maps_to_refusal():
    import qnexus.exceptions as qnx_exc

    err = _tool_error(qnx_exc.NoUniqueMatch())
    assert isinstance(err, ToolError) and "Nothing was changed" in str(err)


def test_secretlike_values_never_reach_the_mapped_message():
    import qnexus.exceptions as qnx_exc

    leaky = qnx_exc.JobError("failed; token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0 leaked")
    err = _tool_error(leaky)
    assert isinstance(err, ToolError) and "eyJ" not in str(err)


def test_network_error_maps_to_actionable_message():
    import httpx

    err = _tool_error(httpx.ConnectError("dns fail"))
    assert isinstance(err, ToolError) and "network" in str(err).lower()


def test_invalid_base64_program_is_rejected_before_any_network_call():
    with pytest.raises(ToolError, match="not valid base64"):
        QnexusClient().upload_program("!!not-base64!!", "proj", "prog")


# --- submit rate limiting ---------------------------------------------------------------------


def test_rate_limiter_blocks_seventh_submit_in_a_minute():
    t = {"now": 0.0}
    limiter = SubmitRateLimiter(max_per_minute=6, now=lambda: t["now"])
    for _ in range(6):
        limiter.check()
    with pytest.raises(RateLimited, match="per minute"):
        limiter.check()
    t["now"] = 61.0  # window slides -> allowed again
    limiter.check()


async def test_submit_tool_is_rate_limited(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    ctx = _ctx(fake_client, cfg)
    for _ in range(6):
        await nexus_submit(ctx, circuit="OPENQASM 2.0;")
    with pytest.raises(RateLimited):
        await nexus_submit(ctx, circuit="OPENQASM 2.0;")


# --- project allowlist (--projects) -----------------------------------------------------------


def test_allowlist_none_allows_everything():
    check_project_allowed(ServerConfig(), None)
    check_project_allowed(ServerConfig(), "anything")


def test_allowlist_blocks_default_project_when_not_listed():
    cfg = ServerConfig(projects=frozenset({"sandbox"}))
    with pytest.raises(ProjectDenied, match="qnexus-mcp"):
        check_project_allowed(cfg, None)  # None resolves to the default project


async def test_submit_blocked_outside_allowlist(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), projects=frozenset({"sandbox"}))
    with pytest.raises(ProjectDenied):
        await nexus_submit(_ctx(fake_client, cfg), circuit="OPENQASM 2.0;", project="other")
    out = await nexus_submit(_ctx(fake_client, cfg), circuit="OPENQASM 2.0;", project="sandbox")
    assert out["job_id"] == "j-new"


async def test_create_project_blocked_outside_allowlist(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "manage"}), projects=frozenset({"sandbox"}))
    with pytest.raises(ProjectDenied):
        await nexus_create_project(_ctx(fake_client, cfg), name="rogue")


# --- quota pre-check (DESIGN §6 Layer 3) ------------------------------------------------------


async def test_billable_emulator_denied_when_quota_exhausted():
    async def yes(_msg):
        return True

    async def quota_empty(_name):
        return False

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    with pytest.raises(SpendDenied, match="quota"):
        await SpendGuard(cfg).check_and_confirm(
            device="H2-1E", estimated_cost=1.0, confirm=yes, quota_check=quota_empty
        )


async def test_hardware_skips_simulation_quota_check():
    async def yes(_msg):
        return True

    async def quota_empty(_name):  # would fail if consulted; hardware must not consult it
        return False

    cfg = ServerConfig(
        toolsets=frozenset({"read", "execute"}),
        allow_spend=True,
        allow_hardware=True,
        max_credits=10.0,
    )
    await SpendGuard(cfg).check_and_confirm(
        device="H2-1", estimated_cost=1.0, confirm=yes, quota_check=quota_empty
    )


async def test_flag_precheck_runs_before_estimation(fake_client):
    """A forbidden device must be denied before any estimate call reaches the client."""
    calls = []

    class TrackingClient:
        def __getattr__(self, item):
            return getattr(fake_client, item)

        def estimate_cost(self, circuit, n_shots, device):
            calls.append("estimate")
            return 3.0

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))  # allow_spend False
    with pytest.raises(SpendDenied):
        await nexus_submit(_ctx(TrackingClient(), cfg), circuit="...", device="H2-1E")
    assert calls == []  # denied without enqueueing a (free) estimation job


# --- device status ----------------------------------------------------------------------------


async def test_device_status_tool_returns_client_data(fake_client, make_ctx):
    out = await nexus_device_status(make_ctx(fake_client), device="H2-1")
    assert out == {"device": "H2-1", "state": "online"}


def test_emulator_status_answered_without_sdk_call():
    out = QnexusClient().device_status("H2-1LE")  # must not touch the network
    assert out["state"] == "online" and "emulator" in out["note"]
