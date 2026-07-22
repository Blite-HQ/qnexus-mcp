"""Execute tools (opt-in via `--toolsets execute`).

Spend is NOT gated at registration: the same submit tool serves the free `H2-1LE` emulator and
billable devices. Billable calls are gated at runtime by SpendGuard: `--allow-spend`, (hardware)
`--allow-hardware`, a `--max-credits` ceiling, a "simulation" quota pre-check (emulators), and an
in-protocol `ctx.elicit` confirmation. All submissions are rate-limited and serialized.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from ..backends import DEFAULT_DEVICE, is_billable
from ..context import (
    call_sync,
    client_of,
    config_of,
    confirm_from_ctx,
    mutation_lock_of,
    rate_limiter_of,
)
from ..guards import SpendGuard, check_project_allowed
from ..permissions import ToolSpec
from ..polling import poll_job
from ..results import shape_result

# Bound shot counts so an injected loop can't pile unbounded work onto the (free) queue.
Shots = Annotated[int, Field(ge=1, le=100_000)]
# Bound the wait so `nexus_submit_and_wait` can never hang a session indefinitely.
WaitTimeout = Annotated[float, Field(gt=0, le=3600)]
DEFAULT_WAIT_TIMEOUT = 300.0
# Bound batch size so one call can't enqueue unbounded work; the rate limiter additionally
# counts every circuit in the batch against --max-submissions-per-minute.
MAX_BATCH_SIZE = 20
BatchCircuits = Annotated[list[str], Field(min_length=1, max_length=MAX_BATCH_SIZE)]


async def nexus_estimate_cost(
    ctx: Context, circuit: str, n_shots: Shots = 100, device: str = DEFAULT_DEVICE
) -> dict[str, Any]:
    """Estimate the HQC cost of running a QASM circuit (submits a free syntax-check job).

    Defaults to the free H2-1LE emulator, which always estimates 0 HQC.
    """
    check_project_allowed(config_of(ctx), None)
    cost = await call_sync(client_of(ctx).estimate_cost, circuit, n_shots, device)
    return {"device": device, "n_shots": n_shots, "estimated_hqc": cost}


async def nexus_compile(
    ctx: Context, circuit: str, device: str = DEFAULT_DEVICE, project: str | None = None
) -> dict[str, Any]:
    """Compile a QASM circuit to a backend's native gate set.

    Defaults to the free H2-1LE emulator.
    """
    check_project_allowed(config_of(ctx), project)
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).compile, circuit, device, project)


async def nexus_submit(
    ctx: Context,
    circuit: str,
    n_shots: Shots = 100,
    device: str = DEFAULT_DEVICE,
    project: str | None = None,
) -> dict[str, Any]:
    """Submit a QASM circuit for execution.

    Defaults to the free H2-1LE emulator. Billable devices require --allow-spend (and, for real
    hardware, --allow-hardware), stay under --max-credits, and prompt for an explicit confirmation.
    """
    client = client_of(ctx)
    config = config_of(ctx)
    guard = SpendGuard(config)
    check_project_allowed(config, project)
    # Flags first: a device the launch config forbids must not even enqueue an estimate job.
    guard.precheck(device)
    rate_limiter_of(ctx).check()
    estimated = (
        await call_sync(client.estimate_cost, circuit, n_shots, device)
        if is_billable(device)
        else 0.0
    )

    async def quota_check(name: str) -> bool:
        return await call_sync(client.check_quota, name)

    await guard.check_and_confirm(
        device=device,
        estimated_cost=estimated,
        confirm=confirm_from_ctx(ctx),
        quota_check=quota_check,
    )
    key = guard.idempotency_key(
        {"circuit": circuit, "n_shots": n_shots, "device": device, "project": project}
    )
    async with mutation_lock_of(ctx):
        return await call_sync(
            client.submit,
            circuit=circuit,
            n_shots=n_shots,
            device=device,
            project=project,
            max_cost=config.max_credits,
            idempotency_key=key,
        )


async def nexus_submit_batch(
    ctx: Context,
    circuits: BatchCircuits,
    n_shots: Shots = 100,
    device: str = DEFAULT_DEVICE,
    project: str | None = None,
) -> dict[str, Any]:
    """Submit up to 20 QASM circuits as one multi-item Nexus job (e.g. a parameter sweep).

    `n_shots` applies to each circuit; per-circuit results come back in submission order via
    nexus_get_results. Defaults to the free H2-1LE emulator. Billable devices require
    --allow-spend (and --allow-hardware for hardware), an aggregate estimate under
    --max-credits, and ONE explicit confirmation for the whole batch. Every circuit counts
    against the submission rate limit, so the largest admissible batch is also bounded by
    --max-submissions-per-minute (default 6); a larger batch is rejected with guidance to
    split it.
    """
    client = client_of(ctx)
    config = config_of(ctx)
    guard = SpendGuard(config)
    # Field bounds the MCP schema; re-check here because guards must not rely on client-side
    # validation (direct calls bypass FastMCP).
    if not 1 <= len(circuits) <= MAX_BATCH_SIZE:
        raise ToolError(
            f"Batch size must be between 1 and {MAX_BATCH_SIZE} circuits, got {len(circuits)}. "
            "Nothing was submitted."
        )
    check_project_allowed(config, project)
    guard.precheck(device)
    rate_limiter_of(ctx).check(count=len(circuits))
    shots_list = [n_shots] * len(circuits)
    estimated = (
        await call_sync(client.estimate_cost_batch, list(circuits), shots_list, device)
        if is_billable(device)
        else 0.0
    )

    async def quota_check(name: str) -> bool:
        return await call_sync(client.check_quota, name)

    await guard.check_and_confirm(
        device=device,
        estimated_cost=estimated,
        confirm=confirm_from_ctx(ctx),
        quota_check=quota_check,
        action=f"Submit {len(circuits)} circuits x {n_shots} shots to {device} as one batch job?",
    )
    key = guard.idempotency_key(
        {"circuits": list(circuits), "n_shots": n_shots, "device": device, "project": project}
    )
    max_cost = [config.max_credits] * len(circuits) if config.max_credits else None
    async with mutation_lock_of(ctx):
        return await call_sync(
            client.submit_batch,
            circuits=list(circuits),
            n_shots=shots_list,
            device=device,
            project=project,
            max_cost=max_cost,
            idempotency_key=key,
        )


async def nexus_submit_and_wait(
    ctx: Context,
    circuit: str,
    n_shots: Shots = 100,
    device: str = DEFAULT_DEVICE,
    project: str | None = None,
    timeout: WaitTimeout = DEFAULT_WAIT_TIMEOUT,
) -> dict[str, Any]:
    """Submit a QASM circuit and return its results. Defaults to the free H2-1LE emulator.

    Waits up to `timeout` seconds (default 300, max 3600), reporting queue status as MCP
    progress; on timeout the job keeps running and can be polled with nexus_job_status /
    nexus_get_results. Counts are capped at the top --max-outcomes outcomes by frequency
    (truncation is reported via total_outcomes / omitted_outcomes / omitted_shots).
    """
    job = await nexus_submit(ctx, circuit=circuit, n_shots=n_shots, device=device, project=project)
    client = client_of(ctx)
    job_id: str = job["job_id"]

    async def status_fn() -> dict[str, Any]:
        return await call_sync(client.job_status, job_id)

    async def report(progress: float, total: float, message: str) -> None:
        await ctx.report_progress(progress=progress, total=total, message=message)

    await poll_job(status_fn, job_id=job_id, timeout=timeout, report=report)
    raw = await call_sync(client.get_results, job_id)
    return shape_result(job_id, raw["counts_list"], config_of(ctx).max_outcomes)


def _spec(fn: Callable[..., Any], is_spend: bool = False) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="execute",
        handler=fn,
        read_only=False,
        idempotent=False,
        is_spend=is_spend,
        description=inspect.cleandoc(fn.__doc__ or ""),
    )


EXECUTE_SPECS: list[ToolSpec] = [
    _spec(nexus_estimate_cost),
    _spec(nexus_compile),
    _spec(nexus_submit, is_spend=True),
    _spec(nexus_submit_batch, is_spend=True),
    _spec(nexus_submit_and_wait, is_spend=True),
]
