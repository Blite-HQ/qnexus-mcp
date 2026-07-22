import base64
import types

import pytest
from fastmcp.exceptions import ToolError

from qnexus_mcp.client import NexusClient, QnexusClient, _parse_qasm


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


def test_job_status_unknown_id_gives_actionable_message(monkeypatch):
    # Found live: qnx.jobs.get(id=...) doesn't raise ZeroMatches for an unknown id the way
    # projects.get(name=...) does -- it raises a bare KeyError from inside the SDK's own response
    # parsing, which _tool_error didn't map, so it surfaced as an opaque "Error calling tool".
    class _FakeJobs:
        @staticmethod
        def get(id):
            raise KeyError("message")

        @staticmethod
        def status(job):  # pragma: no cover - not reached, _get_job raises first
            raise AssertionError("should not be called: _get_job must raise before this")

    class _FakeQnx:
        jobs = _FakeJobs()

    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: _FakeQnx())
    with pytest.raises(ToolError, match="No Nexus job matches id 'bogus'"):
        QnexusClient().job_status(job_id="bogus")


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


def test_parse_qasm_rejects_malformed_circuit_with_actionable_message():
    # Found live: a syntax typo previously escaped _tool_error's mapping entirely and
    # surfaced as a bare "Error calling tool" with zero detail (mask_error_details
    # swallowed the raw lark parser exception) -- an agent had nothing to self-correct
    # from. "OPENQASM 3;" is missing the required decimal version (e.g. "3.0").
    with pytest.raises(ToolError, match="Invalid OpenQASM 2 circuit"):
        _parse_qasm("OPENQASM 3;")


def test_parse_qasm_accepts_valid_circuit():
    qasm = (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        "qreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\n"
    )
    assert _parse_qasm(qasm).n_qubits == 1


def test_list_devices_strips_non_json_serializable_backend_info(monkeypatch):
    import json

    class _UnserializableBackendInfo:
        """Stands in for pytket's real BackendInfo (an architecture graph + OpType
        gate-set) which has no JSON representation and previously broke MCP
        structured output (found live via a real stdio client round-trip)."""

        architecture = types.SimpleNamespace(nodes=[object()] * 5)

    class _FakeDataframe:
        def to_dict(self, orient):
            return [
                {
                    "backend_name": "H2",
                    "device_name": "H2-1LE",
                    "nexus_hosted": True,
                    "backend_info": _UnserializableBackendInfo(),
                }
            ]

    class _FakeDevices:
        @staticmethod
        def get_all():
            return types.SimpleNamespace(df=lambda: _FakeDataframe())

    class _FakeQnx:
        devices = _FakeDevices()

    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: _FakeQnx())
    rows = QnexusClient().list_devices()
    assert rows == [
        {"backend_name": "H2", "device_name": "H2-1LE", "nexus_hosted": True, "n_qubits": 5}
    ]
    json.dumps(rows)  # must not raise: this is exactly what MCP structured_content needs


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
