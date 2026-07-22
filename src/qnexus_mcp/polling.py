"""Tool-layer job polling with progress reporting.

Replaces the SDK's blocking `qnx.jobs.wait_for` for `nexus_submit_and_wait`: wait_for has no
progress hook, so a queued job looked hung for up to the full timeout (audit finding). Each poll
is one cheap status-only GET (`client.job_status`), and every iteration reports elapsed/timeout
plus the live status through MCP progress (a graceful no-op when the client sent no
progressToken). `sleep` and `clock` are injectable so tests are deterministic and instant.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from fastmcp.exceptions import ToolError

from .sanitize import redact

# Failure statuses that end a poll immediately. CANCELLING and RETRYING are transient states in
# qnexus 0.46's JobStatusEnum and keep polling.
TERMINAL_FAILURES = frozenset({"ERROR", "CANCELLED", "TERMINATED", "DEPLETED"})

POLL_INITIAL_INTERVAL = 2.0
POLL_BACKOFF_FACTOR = 1.5
POLL_MAX_INTERVAL = 15.0
# One network blip must not abort a wait on an ALREADY-submitted job (that error message would
# bait a duplicate submit). Give up only after this many consecutive status-check failures.
MAX_CONSECUTIVE_STATUS_FAILURES = 3

StatusFn = Callable[[], Awaitable[dict[str, Any]]]
ReportFn = Callable[[float, float, str], Awaitable[None]]


def _describe(status: dict[str, Any]) -> str:
    state = str(status.get("status", "")).upper()
    queue_position = status.get("queue_position")
    if queue_position is not None:
        return f"{state} (queue position {queue_position})"
    return state


async def poll_job(
    status_fn: StatusFn,
    *,
    job_id: str,
    timeout: float,
    report: ReportFn,
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    clock: Callable[[], float] = time.monotonic,
    initial: float = POLL_INITIAL_INTERVAL,
    factor: float = POLL_BACKOFF_FACTOR,
    cap: float = POLL_MAX_INTERVAL,
) -> dict[str, Any]:
    """Poll until COMPLETED (returns the final status), a terminal failure, or the deadline."""
    start = clock()
    interval = initial
    failures = 0
    while True:
        try:
            status = await status_fn()
        except Exception as exc:
            failures += 1
            if failures >= MAX_CONSECUTIVE_STATUS_FAILURES:
                detail = str(redact(str(exc)))[:200]
                raise ToolError(
                    f"Lost contact with Nexus while waiting for job {job_id} ({failures} "
                    f"consecutive status checks failed; last error: {detail}). The job was "
                    "ALREADY SUBMITTED and may still be running. Do not resubmit; poll "
                    "nexus_job_status and fetch nexus_get_results when it is COMPLETED."
                ) from exc
            remaining = timeout - (clock() - start)
            if remaining <= 0:
                raise ToolError(
                    f"Timed out after {timeout}s waiting for job {job_id}. The job is still "
                    "running on Nexus. Do not resubmit; poll nexus_job_status and fetch "
                    "nexus_get_results when it is COMPLETED."
                ) from exc
            await sleep(min(interval, remaining))
            interval = min(interval * factor, cap)
            continue
        failures = 0
        state = str(status.get("status", "")).upper()
        elapsed = clock() - start
        await report(min(elapsed, timeout), timeout, _describe(status))
        if state == "COMPLETED":
            return status
        if state in TERMINAL_FAILURES:
            detail = status.get("message") or state
            raise ToolError(
                f"Job {job_id} ended as {state}: {detail}. Check nexus_job_status for detail "
                "before deciding whether to resubmit; do not resubmit unchanged."
            )
        remaining = timeout - (clock() - start)
        if remaining <= 0:
            raise ToolError(
                f"Timed out after {timeout}s waiting for job {job_id}. The job is still running "
                "on Nexus. Do not resubmit; poll nexus_job_status and fetch nexus_get_results "
                "when it is COMPLETED."
            )
        await sleep(min(interval, remaining))
        interval = min(interval * factor, cap)
