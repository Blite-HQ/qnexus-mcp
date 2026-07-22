from conftest import FakeClient

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.tools.read import (
    READ_SPECS,
    nexus_get_results,
    nexus_list_devices,
    nexus_list_jobs,
)


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


async def test_list_jobs_returns_paginated_client_data(fake_client, make_ctx):
    out = await nexus_list_jobs(make_ctx(fake_client))
    assert out == {"items": [{"id": "j1", "status": "COMPLETED"}], "returned": 1, "total": 1}


async def test_list_jobs_forwards_filters_to_client(make_ctx):
    calls = {}

    class RecordingClient(FakeClient):
        def list_jobs(self, limit=50, project=None, status=None, name_like=None):
            calls.update(limit=limit, project=project, status=status, name_like=name_like)
            return {"items": [], "returned": 0, "total": 0}

    ctx = make_ctx(RecordingClient())
    await nexus_list_jobs(ctx, limit=10, project="demo", status="RUNNING", name_like="sweep")
    assert calls == {"limit": 10, "project": "demo", "status": "RUNNING", "name_like": "sweep"}


# --- result shaping: top-N truncation + batch items (audit finding #1) ------------------------


async def test_get_results_single_item_shape_keeps_counts_plus_metadata(fake_client, make_ctx):
    out = await nexus_get_results(make_ctx(fake_client), job_id="j1")
    assert out["id"] == "j1"
    assert out["counts"] == {"00": 51, "11": 49}
    assert out["total_outcomes"] == 2 and out["omitted_outcomes"] == 0


async def test_get_results_truncates_to_configured_max_outcomes(make_ctx):
    class ManyOutcomesClient(FakeClient):
        def get_results(self, job_id):
            return {"id": job_id, "counts_list": [{f"{i:04b}": i + 1 for i in range(16)}]}

    ctx = make_ctx(ManyOutcomesClient(), ServerConfig(max_outcomes=3))
    out = await nexus_get_results(ctx, job_id="j1")
    assert len(out["counts"]) == 3
    assert out["counts"] == {"1111": 16, "1110": 15, "1101": 14}  # top-3 by frequency
    assert out["total_outcomes"] == 16
    assert out["omitted_outcomes"] == 13
    assert out["omitted_shots"] == sum(range(1, 14))


async def test_get_results_batch_job_returns_indexed_items(make_ctx):
    ctx = make_ctx(FakeClient(n_result_items=3))
    out = await nexus_get_results(ctx, job_id="j-batch")
    assert out["n_items"] == 3
    assert [item["index"] for item in out["items"]] == [0, 1, 2]
    assert all(item["counts"] == {"00": 51, "11": 49} for item in out["items"])
