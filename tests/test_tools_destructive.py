import types

import pytest

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.context import bind_state
from qnexus_mcp.guards import ConfirmationDenied
from qnexus_mcp.server import build_server, registered_tool_names
from qnexus_mcp.tools.destructive import DESTRUCTIVE_SPECS, nexus_delete_project


class _Elicit:
    def __init__(self, accept: bool = True, data: bool = True) -> None:
        self._accept = accept
        self._data = data

    async def __call__(self, message, response_type=bool):
        action = "accept" if self._accept else "decline"
        return types.SimpleNamespace(action=action, data=self._data)


def _ctx(client, elicit):
    server = types.SimpleNamespace()
    bind_state(server, client, ServerConfig())
    return types.SimpleNamespace(fastmcp=server, elicit=elicit)


def test_destructive_specs_shape():
    assert {s.name for s in DESTRUCTIVE_SPECS} == {
        "nexus_cancel_job",
        "nexus_delete_job",
        "nexus_archive_project",
        "nexus_delete_project",
    }
    assert all(s.toolset == "destructive" and s.is_destructive for s in DESTRUCTIVE_SPECS)


async def test_delete_project_requires_confirmation(fake_client):
    with pytest.raises(ConfirmationDenied):
        await nexus_delete_project(_ctx(fake_client, _Elicit(accept=False)), name="demo")


async def test_delete_project_runs_when_confirmed(fake_client):
    out = await nexus_delete_project(_ctx(fake_client, _Elicit(accept=True)), name="demo")
    assert out == {"name": "demo", "deleted": True}


def test_destructive_gated_by_toolset_and_flag(fake_client):
    base = registered_tool_names(build_server(ServerConfig(), fake_client))
    assert not any("delete" in n for n in base)  # hidden by default

    ts_only = registered_tool_names(
        build_server(ServerConfig(toolsets=frozenset({"read", "destructive"})), fake_client)
    )
    assert not any("delete" in n for n in ts_only)  # toolset alone is not enough

    both = registered_tool_names(
        build_server(
            ServerConfig(toolsets=frozenset({"read", "destructive"}), allow_destructive=True),
            fake_client,
        )
    )
    assert "nexus_delete_project" in both and "nexus_cancel_job" in both
