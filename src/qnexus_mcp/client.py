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
    def create_project(self, name: str, description: str | None = None) -> dict[str, Any]: ...
    def upload_circuit(self, circuit: str, project: str, name: str) -> dict[str, Any]: ...
    def cancel_job(self, job_id: str) -> dict[str, Any]: ...
    def delete_job(self, job_id: str) -> dict[str, Any]: ...
    def archive_project(self, name: str) -> dict[str, Any]: ...
    def delete_project(self, name: str) -> dict[str, Any]: ...


def _qnx() -> Any:
    import qnexus

    return qnexus


def _pytket_qasm() -> Any:
    import pytket.qasm

    return pytket.qasm


def _bitstrings(counts: Any) -> dict[str, int]:
    """Format a pytket counts mapping (tuple keys like (0, 1)) as bitstring -> count."""
    out: dict[str, int] = {}
    for key, value in counts.items():
        bits = "".join(str(b) for b in key) if isinstance(key, (tuple, list)) else str(key)
        out[bits] = int(value)
    return out


def _records(dataframable: Any) -> list[dict[str, Any]]:
    """qnexus returns DataframableList; .df() -> pandas -> list of plain, redacted dicts."""
    rows: list[dict[str, Any]] = [
        redact(row) for row in dataframable.df().to_dict(orient="records")
    ]
    return rows


class QnexusClient:
    """Real implementation over the qnexus SDK (read + execute paths verified live 2026-07-21)."""

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
        # NOTE: jobs.get_all() (the LIST endpoint) was observed returning 500 / server-side
        # timeouts on the event account (2026-07-21). submit/status/results-by-id are unaffected.
        return _records(_qnx().jobs.get_all())

    def job_status(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        st = qnx.jobs.status(qnx.jobs.get(id=job_id))
        out: dict[str, Any] = redact(
            {
                "id": job_id,
                "status": str(getattr(st.status, "value", st.status)),
                "message": getattr(st, "message", None),
                "queue_position": getattr(st, "queue_position", None),
            }
        )
        return out

    def job_cost(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)
        out: dict[str, Any] = redact({"id": job_id, "hqc_cost": qnx.jobs.cost(job)})
        return out

    def get_results(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        result = qnx.jobs.results(qnx.jobs.get(id=job_id))[0].download_result()
        out: dict[str, Any] = redact({"id": job_id, "counts": _bitstrings(result.get_counts())})
        return out

    # --- execute path (all VERIFY LIVE against the real SDK at M2.2 smoke) -------------------

    def _upload(self, qnx: Any, circuit: str, project: str | None) -> tuple[Any, Any]:
        circ = _pytket_qasm().circuit_from_qasm_str(circuit)  # OpenQASM 2 (verified live)
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
        config = qnx.QuantinuumConfig(device_name=device)
        tag = idempotency_key or "job"
        compiled = qnx.compile(
            programs=[circ_ref],
            backend_config=config,
            name=f"qnexus-mcp-compile-{tag}",
            project=project_ref,
        )
        job = qnx.start_execute_job(
            programs=[compiled[0]],
            n_shots=[n_shots],
            backend_config=config,
            name=f"qnexus-mcp-{tag}",
            project=project_ref,
            max_cost=[max_cost] if max_cost else [],
            valid_check=True,
        )
        out: dict[str, Any] = redact({"job_id": str(job.id), "device": device})
        return out

    def wait_and_results(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        qnx = _qnx()
        job = qnx.jobs.get(id=job_id)
        qnx.jobs.wait_for(job, timeout=timeout)
        result = qnx.jobs.results(job)[0].download_result()
        out: dict[str, Any] = redact({"job_id": job_id, "counts": _bitstrings(result.get_counts())})
        return out

    # --- manage (opt-in via --toolsets manage) ------------------------------------------------

    def create_project(self, name: str, description: str | None = None) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get_or_create(name=name, description=description)
        out: dict[str, Any] = redact({"name": name, "id": str(getattr(proj, "id", proj))})
        return out

    def upload_circuit(self, circuit: str, project: str, name: str) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get_or_create(name=project)
        circ = _pytket_qasm().circuit_from_qasm_str(circuit)
        ref = qnx.circuits.upload(circuit=circ, name=name, project=proj)
        out: dict[str, Any] = redact(
            {"name": name, "id": str(getattr(ref, "id", ref)), "project": project}
        )
        return out

    # --- destructive (opt-in via --toolsets destructive + --allow-destructive) ----------------
    # VERIFY LIVE WITH CARE: these delete/cancel real resources; NOT exercised by the live smoke.
    # projects.get(name_like=) must be confirmed to resolve exactly one project before enabling.

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        qnx.jobs.cancel(qnx.jobs.get(id=job_id))
        return {"job_id": job_id, "cancelled": True}

    def delete_job(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        qnx.jobs.delete(qnx.jobs.get(id=job_id))
        return {"job_id": job_id, "deleted": True}

    def archive_project(self, name: str) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get(name_like=name)  # VERIFY LIVE: exact get-by-name filter
        qnx.projects.update(proj, archive=True)
        return {"name": name, "archived": True}

    def delete_project(self, name: str) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get(name_like=name)  # VERIFY LIVE: exact get-by-name filter
        qnx.projects.delete(proj)
        return {"name": name, "deleted": True}
