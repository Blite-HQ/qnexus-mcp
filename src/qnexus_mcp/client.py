"""Thin, injectable wrapper over qnexus. NEVER reads, stores, or returns the auth token.

The `NexusClient` Protocol is what tools depend on; `QnexusClient` is the real implementation and
`FakeClient` (tests/conftest.py) is the offline stand-in. Read and execute signatures are verified
against live Nexus (2026-07-21, Bell state on H2-1LE); the remaining surface is verified against the
installed qnexus 0.46 source.

Every public `QnexusClient` method is wrapped by `@_mapped`, which translates SDK and network
failures into short, actionable, secret-redacted `ToolError` messages (see `_tool_error`). Raw
exceptions never reach the agent: FastMCP masks them into an unactionable generic error.
"""

from __future__ import annotations

import base64
import binascii
import functools
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

from fastmcp.exceptions import ToolError

from .backends import is_billable, is_hardware
from .config import DEFAULT_PROJECT
from .sanitize import redact

_F = TypeVar("_F", bound=Callable[..., Any])

_MAX_PROGRAM_BYTES = 5 * 1024 * 1024  # cap uploaded QIR programs at 5 MiB


@runtime_checkable
class NexusClient(Protocol):
    def auth_status(self) -> dict[str, Any]: ...
    def whoami(self) -> dict[str, Any]: ...
    def list_devices(self) -> list[dict[str, Any]]: ...
    def device_status(self, device: str) -> dict[str, Any]: ...
    def list_projects(self) -> list[dict[str, Any]]: ...
    def get_quota(self) -> list[dict[str, Any]]: ...
    def check_quota(self, name: str) -> bool: ...
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
    def upload_program(self, program_base64: str, project: str, name: str) -> dict[str, Any]: ...
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


def _parse_qasm(circuit: str) -> Any:
    """Parse OpenQASM 2, translating any parse failure into an actionable ToolError.

    circuit_from_qasm_str raises raw lark parser exceptions (UnexpectedToken,
    UnexpectedCharacters, ...) on malformed input -- unmapped by _tool_error, so
    mask_error_details previously turned a simple syntax typo into a bare "Error
    calling tool" with zero detail (found live: an agent has no way to self-correct
    from that). This is pure local parsing (no side effects), so a broad catch here
    is safe and precise.
    """
    try:
        return _pytket_qasm().circuit_from_qasm_str(circuit)
    except Exception as exc:
        raise ToolError(
            f"Invalid OpenQASM 2 circuit: {str(exc)[:300]}. Fix the syntax and retry; "
            "nothing was uploaded."
        ) from None


def _get_job(qnx: Any, job_id: str) -> Any:
    """Resolve a job by id, translating an unknown id into an actionable ToolError.

    qnx.jobs.get(id=...) doesn't raise qnexus.exceptions.ZeroMatches for a bad id the way
    projects.get(name=...) does -- it raises a bare KeyError('message') from inside the SDK's own
    response parsing (found live: an unknown job id surfaced as an opaque "Error calling tool" with
    zero detail, since _tool_error only maps qnexus/httpx exception types). Give it the same
    actionable shape as the project-lookup case.
    """
    try:
        return qnx.jobs.get(id=job_id)
    except KeyError:
        raise ToolError(
            f"No Nexus job matches id '{job_id}'. Check the id with nexus_list_jobs; "
            "nothing was changed."
        ) from None


def _tool_error(exc: Exception) -> ToolError | None:
    """Map a qnexus/network exception to an actionable, safe ToolError (or None to re-raise)."""
    try:
        import qnexus.exceptions as qnx_exc
    except ImportError:  # pragma: no cover - qnexus is a hard dependency
        return None
    import httpx

    def detail(e: Exception) -> str:
        return str(redact(str(e)))[:300]

    if isinstance(exc, qnx_exc.AuthenticationError):
        return ToolError(
            "Not authenticated with Nexus (or the session expired). "
            "Run `qnx login` in a terminal, then retry."
        )
    if isinstance(exc, qnx_exc.ZeroMatches):
        return ToolError(
            "No Nexus resource matches that exact name. "
            "Check the name with nexus_list_projects / nexus_list_jobs; nothing was changed."
        )
    if isinstance(exc, qnx_exc.NoUniqueMatch):
        return ToolError(
            "More than one Nexus resource matches; refusing to act on an ambiguous target. "
            "List projects/jobs to find the exact id and retry with that. Nothing was changed."
        )
    if isinstance(exc, qnx_exc.JobError):
        return ToolError(
            f"Nexus job failed: {detail(exc)}. Check nexus_job_status for detail before "
            "deciding whether to resubmit; do not resubmit unchanged."
        )
    if isinstance(
        exc,
        (
            qnx_exc.ResourceFetchFailed,
            qnx_exc.ResourceCreateFailed,
            qnx_exc.ResourceDeleteFailed,
            qnx_exc.ResourceUpdateFailed,
        ),
    ):
        status = getattr(exc, "status_code", None)
        if isinstance(status, int) and status >= 500:
            return ToolError(
                f"Nexus returned a server error ({status}). This is a Nexus-side issue, not a "
                "problem with your request; do not retry in a loop, try again later. "
                "Other endpoints (e.g. job status by id) may still work."
            )
        return ToolError(f"Nexus rejected the request (HTTP {status}): {detail(exc)}")
    if isinstance(exc, httpx.TimeoutException):
        return ToolError(
            "The request to Nexus timed out. The service may be slow or unreachable. "
            "retry once; if it persists, stop and report the outage to the user."
        )
    if isinstance(exc, httpx.HTTPError):
        return ToolError(
            "Could not reach the Nexus API (network error). Check connectivity, then retry once."
        )
    return None


def _mapped(fn: _F) -> _F:
    """Translate SDK/network exceptions raised by a client method into ToolErrors."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except Exception as exc:
            mapped = _tool_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise

    return wrapper  # type: ignore[return-value]


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
    """Real implementation over the qnexus SDK (read + execute paths verified live 2026-07-21).

    All methods are synchronous and blocking (the SDK is sync httpx; `jobs.wait_for` even runs its
    own `asyncio.run`). Tools MUST call them through `context.call_sync`, never directly from the
    event loop.
    """

    @_mapped
    def auth_status(self) -> dict[str, Any]:
        qnx = _qnx()
        logged_in = bool(qnx.auth.is_logged_in())
        return {"logged_in": logged_in, "hint": None if logged_in else "run: qnx login"}

    @_mapped
    def whoami(self) -> dict[str, Any]:
        records = _records(_qnx().users.get_self())
        return records[0] if records else {}

    @_mapped
    def list_devices(self) -> list[dict[str, Any]]:
        # devices.get_all() rows carry a raw pytket BackendInfo (architecture graph,
        # OpType gate-set) that pydantic can't serialize to JSON, which silently drops
        # MCP structured_content, which a strict client then rejects as a schema
        # violation (found live: nexus_list_devices via a real stdio MCP round-trip).
        # Surface only the plain, agent-useful fields instead of the raw SDK object.
        rows = _qnx().devices.get_all().df().to_dict(orient="records")
        out: list[dict[str, Any]] = []
        for row in rows:
            info = row.get("backend_info")
            architecture = getattr(info, "architecture", None)
            nodes = getattr(architecture, "nodes", None)
            out.append(
                redact(
                    {
                        "backend_name": row.get("backend_name"),
                        "device_name": row.get("device_name"),
                        "nexus_hosted": row.get("nexus_hosted"),
                        "n_qubits": len(nodes) if nodes is not None else None,
                    }
                )
            )
        return out

    @_mapped
    def device_status(self, device: str) -> dict[str, Any]:
        # The SDK only reports status for hardware-hosted devices; it documents cloud-hosted
        # emulators/syntax checkers as "always online" and rejects them, so we answer directly.
        if not is_hardware(device):
            return {
                "device": device,
                "state": "online",
                "note": "emulators and syntax checkers are cloud-hosted and always available",
            }
        qnx = _qnx()
        state = qnx.devices.status(qnx.QuantinuumConfig(device_name=device))
        out: dict[str, Any] = redact(
            {"device": device, "state": str(getattr(state, "value", state))}
        )
        return out

    @_mapped
    def list_projects(self) -> list[dict[str, Any]]:
        return _records(_qnx().projects.get_all())

    @_mapped
    def get_quota(self) -> list[dict[str, Any]]:
        return _records(_qnx().quotas.get_all())

    @_mapped
    def check_quota(self, name: str) -> bool:
        return bool(_qnx().quotas.check_quota(name))

    @_mapped
    def list_jobs(self) -> list[dict[str, Any]]:
        # NOTE: jobs.get_all() (the LIST endpoint) was observed returning 500 / server-side
        # timeouts on the event account (2026-07-21). submit/status/results-by-id are unaffected.
        # _tool_error turns that 500 into a clear "Nexus-side issue, don't retry-loop" message.
        return _records(_qnx().jobs.get_all())

    @_mapped
    def job_status(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        st = qnx.jobs.status(_get_job(qnx, job_id))
        out: dict[str, Any] = redact(
            {
                "id": job_id,
                "status": str(getattr(st.status, "value", st.status)),
                "message": getattr(st, "message", None),
                "queue_position": getattr(st, "queue_position", None),
            }
        )
        return out

    @_mapped
    def job_cost(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        job = _get_job(qnx, job_id)
        out: dict[str, Any] = redact({"id": job_id, "hqc_cost": qnx.jobs.cost(job)})
        return out

    @_mapped
    def get_results(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        refs = qnx.jobs.results(_get_job(qnx, job_id))
        if not refs:
            raise ToolError(
                f"Job {job_id} has no results yet. Check nexus_job_status; only COMPLETED jobs "
                "have results."
            )
        # One ref per job item, in submission order: a multi-circuit (batch) job returns every
        # item's counts, not just the first (audit fix).
        counts_list = [_bitstrings(ref.download_result().get_counts()) for ref in refs]
        out: dict[str, Any] = redact({"id": job_id, "counts_list": counts_list})
        return out

    # --- execute path (verified live at the M2.2 smoke) ---------------------------------------

    def _upload(self, qnx: Any, circuit: str, project: str | None) -> tuple[Any, Any]:
        circ = _parse_qasm(circuit)
        project_ref = qnx.projects.get_or_create(name=project or DEFAULT_PROJECT)
        circ_ref = qnx.circuits.upload(circuit=circ, name="qnexus-mcp-circuit", project=project_ref)
        return circ_ref, project_ref

    @_mapped
    def estimate_cost(self, circuit: str, n_shots: int, device: str) -> float:
        qnx = _qnx()
        circ_ref, _ = self._upload(qnx, circuit, None)
        cost = qnx.circuits.cost(circ_ref, n_shots, qnx.QuantinuumConfig(device_name=device))
        if cost is None and is_billable(device):
            # Never let a missing estimate read as "0 HQC": the --max-credits gate and the user's
            # confirmation would both be based on a fiction. Refuse instead.
            raise ToolError(
                f"Nexus returned no cost estimate for {device}; refusing to treat that as free. "
                "Retry, or use the free H2-1LE emulator."
            )
        return float(cost or 0.0)

    @_mapped
    def compile(self, circuit: str, device: str, project: str | None = None) -> dict[str, Any]:
        qnx = _qnx()
        circ_ref, project_ref = self._upload(qnx, circuit, project)
        compiled = qnx.compile(
            programs=[circ_ref],
            backend_config=qnx.QuantinuumConfig(device_name=device),
            name="qnexus-mcp-compile",
            project=project_ref,
        )
        compiled_id = str(getattr(compiled[0], "id", compiled[0]))
        out: dict[str, Any] = redact({"device": device, "compiled": compiled_id})
        return out

    @_mapped
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

    @_mapped
    def wait_and_results(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        import asyncio

        qnx = _qnx()
        job = _get_job(qnx, job_id)
        try:
            # SDK default HybridStrategy: websocket first, exponential-backoff polling fallback.
            qnx.jobs.wait_for(job, timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            raise ToolError(
                f"Timed out after {timeout}s waiting for job {job_id}. The job is still running "
                "on Nexus. Do not resubmit; poll nexus_job_status and fetch nexus_get_results "
                "when it is COMPLETED."
            ) from None
        refs = qnx.jobs.results(job)
        if not refs:
            raise ToolError(
                f"Job {job_id} finished but returned no results. Check nexus_job_status."
            )
        result = refs[0].download_result()
        out: dict[str, Any] = redact({"job_id": job_id, "counts": _bitstrings(result.get_counts())})
        return out

    # --- manage (opt-in via --toolsets manage) ------------------------------------------------

    @_mapped
    def create_project(self, name: str, description: str | None = None) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get_or_create(name=name, description=description)
        out: dict[str, Any] = redact({"name": name, "id": str(getattr(proj, "id", proj))})
        return out

    @_mapped
    def upload_circuit(self, circuit: str, project: str, name: str) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get_or_create(name=project)
        circ = _parse_qasm(circuit)
        ref = qnx.circuits.upload(circuit=circ, name=name, project=proj)
        out: dict[str, Any] = redact(
            {"name": name, "id": str(getattr(ref, "id", ref)), "project": project}
        )
        return out

    @_mapped
    def upload_program(self, program_base64: str, project: str, name: str) -> dict[str, Any]:
        try:
            data = base64.b64decode(program_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ToolError("program_base64 is not valid base64. Nothing was uploaded.") from None
        if len(data) > _MAX_PROGRAM_BYTES:
            raise ToolError(
                f"Program exceeds the {_MAX_PROGRAM_BYTES // (1024 * 1024)} MiB upload cap. "
                "Nothing was uploaded."
            )
        qnx = _qnx()
        proj = qnx.projects.get_or_create(name=project)
        ref = qnx.qir.upload(qir=data, name=name, project=proj)
        out: dict[str, Any] = redact(
            {"name": name, "id": str(getattr(ref, "id", ref)), "project": project}
        )
        return out

    # --- destructive (opt-in via --toolsets destructive + --allow-destructive) ----------------
    # Project targets resolve via projects.get(name=...): the SDK's EXACT-match filter
    # (name_exact server-side) which raises ZeroMatches / NoUniqueMatch instead of guessing.
    # Never use name_like (substring) here: it could resolve the wrong project.

    @_mapped
    def cancel_job(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        qnx.jobs.cancel(_get_job(qnx, job_id))
        out: dict[str, Any] = redact({"job_id": job_id, "cancelled": True})
        return out

    @_mapped
    def delete_job(self, job_id: str) -> dict[str, Any]:
        qnx = _qnx()
        qnx.jobs.delete(_get_job(qnx, job_id))
        out: dict[str, Any] = redact({"job_id": job_id, "deleted": True})
        return out

    @_mapped
    def archive_project(self, name: str) -> dict[str, Any]:
        qnx = _qnx()
        proj = qnx.projects.get(name=name)  # exact match; raises on 0 or >1 matches
        qnx.projects.update(proj, archive=True)
        out: dict[str, Any] = redact({"name": name, "archived": True})
        return out

    @_mapped
    def delete_project(self, name: str) -> dict[str, Any]:
        import qnexus.exceptions as qnx_exc

        qnx = _qnx()
        try:
            proj = qnx.projects.get(name=name, is_archived=True)  # exact match; must be archived
        except qnx_exc.ZeroMatches:
            raise ToolError(
                f"No archived project is named exactly '{name}'. Deletion requires the project "
                "to be archived first (nexus_archive_project). Nothing was deleted."
            ) from None
        qnx.projects.delete(proj)
        out: dict[str, Any] = redact({"name": name, "deleted": True})
        return out
