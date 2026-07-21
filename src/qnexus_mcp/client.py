"""Thin, injectable wrapper over qnexus. NEVER reads, stores, or returns the auth token.

The `NexusClient` Protocol is what tools depend on; `QnexusClient` is the real implementation and
`FakeClient` (tests/conftest.py) is the offline stand-in. Signatures follow
docs/research/04-qnexus-sdk-surface.md; items marked VERIFY LIVE are confirmed against the installed
SDK by the M1.9 live smoke test (which needs `qnx login`).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .sanitize import redact


@runtime_checkable
class NexusClient(Protocol):
    def auth_status(self) -> dict[str, Any]: ...
    def whoami(self) -> dict[str, Any]: ...
    def list_devices(self) -> list[dict[str, Any]]: ...
    def list_projects(self) -> list[dict[str, Any]]: ...
    def get_quota(self) -> list[dict[str, Any]]: ...
    def list_jobs(self) -> list[dict[str, Any]]: ...
    def job_status(self, job_id: str) -> dict[str, Any]: ...
    def job_cost(self, job_id: str) -> dict[str, Any]: ...
    def get_results(self, job_id: str) -> dict[str, Any]: ...
    def estimate_cost(self, circuit: str, n_shots: int, device: str) -> float: ...
    def compile(self, circuit: str, device: str, project: str | None = None) -> dict[str, Any]: ...
    def submit(
        self,
        circuit: str,
        n_shots: int,
        device: str,
        project: str | None = None,
        max_cost: float | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]: ...
    def wait_and_results(self, job_id: str, timeout: float | None = None) -> dict[str, Any]: ...


def _qnx() -> Any:
    import qnexus

    return qnexus


def _pytket_qasm() -> Any:
    import pytket.qasm

    return pytket.qasm


def _records(dataframable: Any) -> list[dict[str, Any]]:
    """qnexus returns DataframableList; .df() -> pandas -> list of plain, redacted dicts."""
    rows: list[dict[str, Any]] = [
        redact(row) for row in dataframable.df().to_dict(orient="records")
    ]
    return rows


class QnexusClient:
    """Real implementation over the qnexus SDK (VERIFY LIVE signatures at M1.9)."""

    def auth_status(self) -> dict[str, Any]:
        qnx = _qnx()
        logged_in = bool(qnx.auth.is_logged_in())
        return {"logged_in": logged_in, "hint": None if logged_in else "run: qnx login"}

    def whoami(self) -> dict[str, Any]:
        records = _records(_qnx().users.get_self())  # VERIFY LIVE: get_self df shape
        return records[0] if records else {}

    def list_devices(self) -> list[dict[str, Any]]:
        return _records(_qnx().devices.get_all())

    def list_projects(self) -> list[dict[str, Any]]:
        return _records(_qnx().projects.get_all())

    def get_quota(self) -> list[dict[str, Any]]:
        return _records(_qnx().quotas.get_all())

    def list_jobs(self) -> list[dict[str, Any]]:
        return _records(_qnx().jobs.get_all())

    def job_status(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)  # VERIFY LIVE: get-by-id kwarg
        out: dict[str, Any] = redact({"id": job_id, "status": str(qnx.jobs.status(job))})
        return out

    def job_cost(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)
        out: dict[str, Any] = redact({"id": job_id, "hqc_cost": qnx.jobs.cost(job)})
        return out

    def get_results(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)
        result = qnx.jobs.results(job)[0].download_result()  # VERIFY LIVE signatures
        counts = {str(k): int(v) for k, v in result.get_counts().items()}
        out: dict[str, Any] = redact({"id": job_id, "counts": counts})
        return out

    # --- execute path (all VERIFY LIVE against the real SDK at M2.2 smoke) -------------------

    def _upload(self, qnx: Any, circuit: str, project: str | None) -> tuple[Any, Any]:
        circ = _pytket_qasm().circuit_from_qasm_str(circuit)  # VERIFY LIVE: QASM3 parse entrypoint
        project_ref = qnx.projects.get_or_create(name=project or "qnexus-mcp")
        circ_ref = qnx.circuits.upload(circuit=circ, name="qnexus-mcp-circuit", project=project_ref)
        return circ_ref, project_ref

    def estimate_cost(self, circuit: str, n_shots: int, device: str) -> float:
        qnx = _qnx()
        circ_ref, _ = self._upload(qnx, circuit, None)
        cost = qnx.circuits.cost(circ_ref, n_shots, qnx.QuantinuumConfig(device_name=device))
        return float(cost or 0.0)

    def compile(self, circuit: str, device: str, project: str | None = None) -> dict[str, Any]:
        qnx = _qnx()
        circ_ref, project_ref = self._upload(qnx, circuit, project)
        compiled = qnx.compile(
            programs=[circ_ref],
            backend_config=qnx.QuantinuumConfig(device_name=device),
            name="qnexus-mcp-compile",
            project=project_ref,
        )
        out: dict[str, Any] = redact({"device": device, "compiled": str(compiled[0])})
        return out

    def submit(
        self,
        circuit: str,
        n_shots: int,
        device: str,
        project: str | None = None,
        max_cost: float | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        qnx = _qnx()
        circ_ref, project_ref = self._upload(qnx, circuit, project)
        job = qnx.start_execute_job(
            programs=[circ_ref],
            n_shots=[n_shots],
            backend_config=qnx.QuantinuumConfig(device_name=device),
            name=f"qnexus-mcp-{idempotency_key or 'exec'}",
            project=project_ref,
            max_cost=[max_cost] if max_cost else [],
            valid_check=True,
        )
        out: dict[str, Any] = redact({"job_id": str(getattr(job, "id", job)), "device": device})
        return out

    def wait_and_results(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)
        qnx.jobs.wait_for(job, timeout=timeout)
        result = qnx.jobs.results(job)[0].download_result()
        counts = {str(k): int(v) for k, v in result.get_counts().items()}
        out: dict[str, Any] = redact({"job_id": job_id, "counts": counts})
        return out
