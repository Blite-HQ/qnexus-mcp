import base64

import pytest
from fastmcp.exceptions import ToolError

from qnexus_mcp.client import NexusClient, QnexusClient


def test_fake_client_satisfies_protocol(fake_client):
    assert isinstance(fake_client, NexusClient)


def test_auth_status_shape(fake_client):
    s = fake_client.auth_status()
    assert set(s) == {"logged_in", "hint"}
    assert s["logged_in"] is True


# --- QnexusClient's own logic (not the FakeClient stand-in) --------------------------------
# These exercise real _mapped/error-translation code paths without touching the network, by
# monkeypatching the lazy `_qnx()` import to a minimal stand-in shaped like the qnexus module.


def test_upload_program_rejects_over_cap_size():
    oversized = base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode()
    with pytest.raises(ToolError, match="5 MiB upload cap"):
        QnexusClient().upload_program(program_base64=oversized, project="p", name="n")


def test_upload_program_rejects_invalid_base64():
    with pytest.raises(ToolError, match="not valid base64"):
        QnexusClient().upload_program(program_base64="not-base64!!!", project="p", name="n")


def test_delete_project_requires_archived_first(monkeypatch):
    import qnexus.exceptions as qnx_exc

    class _FakeProjects:
        @staticmethod
        def get(name, is_archived=None):
            raise qnx_exc.ZeroMatches("no archived match")

    class _FakeQnx:
        projects = _FakeProjects()

    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: _FakeQnx())
    with pytest.raises(ToolError, match="Deletion requires the project to be archived first"):
        QnexusClient().delete_project(name="demo")


def test_wait_and_results_timeout_gives_actionable_message(monkeypatch):
    class _FakeJobs:
        @staticmethod
        def get(id):
            return object()

        @staticmethod
        def wait_for(job, timeout=None):
            raise TimeoutError()

        @staticmethod
        def results(job):  # pragma: no cover - not reached, timeout raises first
            return []

    class _FakeQnx:
        jobs = _FakeJobs()

    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: _FakeQnx())
    with pytest.raises(ToolError, match="Timed out after 5s waiting for job j1"):
        QnexusClient().wait_and_results(job_id="j1", timeout=5)
