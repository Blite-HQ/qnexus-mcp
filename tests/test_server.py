from qnexus_mcp.config import ServerConfig
from qnexus_mcp.server import build_server, registered_tool_names


def test_readonly_server_exposes_read_tools(fake_client):
    names = registered_tool_names(build_server(ServerConfig(), fake_client))
    assert {"nexus_auth_status", "nexus_list_devices", "nexus_get_results"} <= names
    assert not any("submit" in n or "delete" in n for n in names)


def test_enabling_execute_toolset_is_accepted(fake_client):
    # Execute tools land in M2; enabling the toolset must not break read-tool exposure.
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    names = registered_tool_names(build_server(cfg, fake_client))
    assert "nexus_list_devices" in names


def test_server_masks_error_details(fake_client):
    # qnexus/httpx exceptions must not reach the LLM verbatim (DESIGN §7/§9).
    server = build_server(ServerConfig(), fake_client)
    assert server._mask_error_details is True


def test_execute_surface_lists_submit_not_destructive(fake_client):
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}))
    names = registered_tool_names(build_server(cfg, fake_client))
    assert {"nexus_submit", "nexus_estimate_cost", "nexus_compile"} <= names
    assert not any("delete" in n or "cancel" in n for n in names)  # destructive stays out
