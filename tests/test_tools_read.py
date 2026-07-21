from qnexus_mcp.tools.read import READ_SPECS, nexus_list_devices, nexus_list_jobs


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


async def test_list_devices_returns_client_data(fake_client, make_ctx):
    out = await nexus_list_devices(make_ctx(fake_client))
    assert out == [{"name": "H2-1LE", "status": "online", "billable": False}]


async def test_list_jobs_passes_filters(fake_client, make_ctx):
    out = await nexus_list_jobs(make_ctx(fake_client), project="p1")
    assert out == [{"id": "j1", "status": "COMPLETED"}]
