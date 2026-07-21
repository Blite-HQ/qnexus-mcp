from qnexus_mcp.tools.manage import MANAGE_SPECS, nexus_create_project


def test_manage_specs_shape():
    assert {s.name for s in MANAGE_SPECS} == {"nexus_create_project", "nexus_upload_circuit"}
    assert all(
        s.toolset == "manage" and not s.read_only and not s.is_destructive for s in MANAGE_SPECS
    )


async def test_create_project_returns_client_data(fake_client, make_ctx):
    out = await nexus_create_project(make_ctx(fake_client), name="demo")
    assert out == {"name": "demo", "id": "proj-new"}
