from qnexus_mcp.config import ServerConfig
from qnexus_mcp.tools.read import READ_SPECS


def _by_name(name):
    return next(s for s in READ_SPECS if s.name == name)


def test_all_read_specs_are_read_only():
    assert READ_SPECS
    assert all(s.read_only and s.toolset == "read" for s in READ_SPECS)


def test_expected_read_tools_present():
    names = {s.name for s in READ_SPECS}
    assert {
        "nexus_auth_status",
        "nexus_list_devices",
        "nexus_get_quota",
        "nexus_list_projects",
        "nexus_get_results",
    } <= names


def test_list_devices_handler_returns_client_data(fake_client):
    out = _by_name("nexus_list_devices").handler(fake_client, ServerConfig(), None)
    assert out == [{"name": "H2-1LE", "status": "online", "billable": False}]
