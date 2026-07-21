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


def _qnx() -> Any:
    import qnexus

    return qnexus


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
