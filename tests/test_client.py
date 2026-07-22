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


class _FakePageIterator:
    """NexusIterator stand-in: yields refs whose .df() is a one-row frame; counts consumption."""

    def __init__(self, rows, total):
        self._rows = rows
        self._total = total
        self.consumed = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.consumed >= len(self._rows):
            raise StopIteration
        row = self._rows[self.consumed]
        self.consumed += 1
        return types.SimpleNamespace(
            df=lambda row=row: types.SimpleNamespace(to_dict=lambda orient: [row])
        )

    def count(self):
        return self._total


def _patch_get_all(monkeypatch, iterator, attr="jobs"):
    calls = {}

    def get_all(**kwargs):
        calls.update(kwargs)
        return iterator

    fake_qnx = types.SimpleNamespace(**{attr: types.SimpleNamespace(get_all=get_all)})
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: fake_qnx)
    return calls


def test_list_jobs_requests_single_page_of_limit_size(monkeypatch):
    it = _FakePageIterator([{"id": f"j{i}"} for i in range(10)], total=40)
    calls = _patch_get_all(monkeypatch, it)
    out = QnexusClient().list_jobs(limit=5)
    assert calls["page_size"] == 5
    assert it.consumed <= 5  # islice stops at the limit; never drains further pages
    assert out["returned"] == 5
    assert out["total"] == 40
    assert out["items"][0] == {"id": "j0"}


def test_list_jobs_maps_status_name_to_enum(monkeypatch):
    from qnexus.models import JobStatusEnum

    it = _FakePageIterator([], total=0)
    calls = _patch_get_all(monkeypatch, it)
    QnexusClient().list_jobs(status="running")
    assert calls["job_status"] == [JobStatusEnum.RUNNING]


def test_list_jobs_invalid_status_raises_tool_error_listing_valid_names(monkeypatch):
    it = _FakePageIterator([], total=0)
    _patch_get_all(monkeypatch, it)
    with pytest.raises(ToolError, match="COMPLETED") as exc:
        QnexusClient().list_jobs(status="bogus")
    assert "bogus" in str(exc.value)


def test_list_jobs_forwards_name_like(monkeypatch):
    it = _FakePageIterator([], total=0)
    calls = _patch_get_all(monkeypatch, it)
    QnexusClient().list_jobs(name_like="sweep")
    assert calls["name_like"] == "sweep"


def test_list_projects_passes_name_like_and_archived(monkeypatch):
    it = _FakePageIterator([{"name": "demo"}], total=1)
    calls = _patch_get_all(monkeypatch, it, attr="projects")
    out = QnexusClient().list_projects(limit=10, name_like="dem", archived=True)
    assert calls["page_size"] == 10
    assert calls["name_like"] == "dem"
    assert calls["is_archived"] is True
    assert out == {"items": [{"name": "demo"}], "returned": 1, "total": 1}


_VALID_QASM = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\n'
)


class _RecordingBatchQnx:
    """Fake qnexus module recording compile/execute calls for batch assertions."""

    def __init__(self, cost=0.0):
        self.execute_calls = []
        self.cost_calls = []
        self.project_names = []
        self._cost = cost

    class QuantinuumConfig:
        def __init__(self, device_name):
            self.device_name = device_name

    @property
    def projects(self):
        def get_or_create(name, description=None):
            self.project_names.append(name)
            return f"proj:{name}"

        return types.SimpleNamespace(get_or_create=get_or_create)

    @property
    def circuits(self):
        def cost(refs, n_shots, config):
            self.cost_calls.append((refs, n_shots, config.device_name))
            return self._cost

        return types.SimpleNamespace(
            upload=lambda circuit, name, project: f"ref:{circuit.n_qubits}", cost=cost
        )

    def compile(self, programs, backend_config, name, project):
        return [f"compiled:{p}" for p in programs]

    def start_execute_job(self, **kwargs):
        self.execute_calls.append(kwargs)
        return types.SimpleNamespace(id="batch-job-1")


def test_submit_batch_compiles_all_and_starts_one_execute_job(monkeypatch):
    qnx = _RecordingBatchQnx()
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    out = QnexusClient().submit_batch(
        circuits=[_VALID_QASM, _VALID_QASM, _VALID_QASM],
        n_shots=[10, 10, 10],
        device="H2-1LE",
    )
    assert out == {"job_id": "batch-job-1", "device": "H2-1LE", "n_circuits": 3}
    assert len(qnx.execute_calls) == 1  # ONE Nexus job for the whole batch
    call = qnx.execute_calls[0]
    assert len(call["programs"]) == 3
    assert call["n_shots"] == [10, 10, 10]


def test_submit_batch_passes_per_item_max_cost_list(monkeypatch):
    qnx = _RecordingBatchQnx()
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    QnexusClient().submit_batch(
        circuits=[_VALID_QASM, _VALID_QASM],
        n_shots=[5, 5],
        device="H2-1E",
        max_cost=[2.5, 2.5],
    )
    assert qnx.execute_calls[0]["max_cost"] == [2.5, 2.5]


def test_estimate_cost_batch_returns_aggregate_float(monkeypatch):
    qnx = _RecordingBatchQnx(cost=7.5)
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    cost = QnexusClient().estimate_cost_batch([_VALID_QASM, _VALID_QASM], [10, 10], "H2-1E")
    assert cost == 7.5
    (refs, n_shots, device) = qnx.cost_calls[0]
    assert len(refs) == 2 and n_shots == [10, 10] and device == "H2-1E"


def test_estimate_cost_uploads_into_the_target_project(monkeypatch):
    qnx = _RecordingBatchQnx(cost=1.0)
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    QnexusClient().estimate_cost(_VALID_QASM, 10, "H2-1E", project="teamA")
    assert qnx.project_names == ["teamA"]


def test_estimate_cost_batch_uploads_into_the_target_project(monkeypatch):
    qnx = _RecordingBatchQnx(cost=1.0)
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    QnexusClient().estimate_cost_batch([_VALID_QASM], [10], "H2-1E", project="teamA")
    assert qnx.project_names == ["teamA"]


def test_estimate_cost_batch_refuses_none_estimate_on_billable_device(monkeypatch):
    qnx = _RecordingBatchQnx(cost=None)
    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: qnx)
    with pytest.raises(ToolError, match="refusing to treat that as free"):
        QnexusClient().estimate_cost_batch([_VALID_QASM], [10], "H2-1E")


def test_get_results_downloads_every_ref_in_submission_order(monkeypatch):
    # Latent bug found by audit: only refs[0] was downloaded, silently dropping every other
    # item of a multi-circuit (batch) job.
    class _FakeRef:
        def __init__(self, counts):
            self._counts = counts

        def download_result(self):
            return types.SimpleNamespace(get_counts=lambda: self._counts)

    class _FakeJobs:
        @staticmethod
        def get(id):
            return object()

        @staticmethod
        def results(job):
            return [_FakeRef({(0, 0): 3}), _FakeRef({(1, 1): 7})]

    class _FakeQnx:
        jobs = _FakeJobs()

    monkeypatch.setattr("qnexus_mcp.client._qnx", lambda: _FakeQnx())
    out = QnexusClient().get_results(job_id="j1")
    assert out == {"id": "j1", "counts_list": [{"00": 3}, {"11": 7}]}
