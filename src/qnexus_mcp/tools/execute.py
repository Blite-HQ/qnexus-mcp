"""Execute tools (opt-in via `--toolsets execute`).

Spend is NOT gated at registration — the same submit tool serves the free `H2-1LE` emulator and
billable devices. Billable calls are gated at runtime by SpendGuard: `--allow-spend`, (hardware)
`--allow-hardware`, a `--max-credits` ceiling, and an in-protocol `ctx.elicit` confirmation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..backends import DEFAULT_DEVICE, is_billable
from ..context import client_of, config_of
from ..guards import Confirm, SpendGuard
from ..permissions import ToolSpec


def _confirm_from_ctx(ctx: Context) -> Confirm:
    async def confirm(message: str) -> bool:
        # response_type=bool is valid at runtime; mypy mis-resolves elicit's overloaded signature.
        result = await ctx.elicit(message, response_type=bool)  # type: ignore[arg-type]
        return getattr(result, "action", None) == "accept" and bool(getattr(result, "data", False))

    return confirm


async def nexus_estimate_cost(
    ctx: Context, circuit: str, n_shots: int = 100, device: str = DEFAULT_DEVICE
) -> dict[str, Any]:
    """Estimate the HQC cost of running a QASM circuit (submits a free syntax-check job)."""
    cost = client_of(ctx).estimate_cost(circuit, n_shots, device)
    return {"device": device, "n_shots": n_shots, "estimated_hqc": cost}


async def nexus_compile(
    ctx: Context, circuit: str, device: str = DEFAULT_DEVICE, project: str | None = None
) -> dict[str, Any]:
    """Compile a QASM circuit to a backend's native gate set."""
    return client_of(ctx).compile(circuit, device, project)


async def nexus_submit(
    ctx: Context,
    circuit: str,
    n_shots: int = 100,
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
    estimated = client.estimate_cost(circuit, n_shots, device) if is_billable(device) else 0.0
    await guard.check_and_confirm(
        device=device, estimated_cost=estimated, confirm=_confirm_from_ctx(ctx)
    )
    key = guard.idempotency_key({"circuit": circuit, "n_shots": n_shots, "device": device})
    return client.submit(
        circuit=circuit,
        n_shots=n_shots,
        device=device,
        project=project,
        max_cost=config.max_credits,
        idempotency_key=key,
    )


async def nexus_submit_and_wait(
    ctx: Context,
    circuit: str,
    n_shots: int = 100,
    device: str = DEFAULT_DEVICE,
    project: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Submit a QASM circuit and return its results. Defaults to the free H2-1LE emulator."""
    job = await nexus_submit(ctx, circuit=circuit, n_shots=n_shots, device=device, project=project)
    return client_of(ctx).wait_and_results(job["job_id"], timeout=timeout)


def _spec(fn: Callable[..., Any], is_spend: bool = False) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="execute",
        handler=fn,
        read_only=False,
        idempotent=False,
        is_spend=is_spend,
        description=(fn.__doc__ or "").strip().splitlines()[0],
    )


EXECUTE_SPECS: list[ToolSpec] = [
    _spec(nexus_estimate_cost),
    _spec(nexus_compile),
    _spec(nexus_submit, is_spend=True),
    _spec(nexus_submit_and_wait, is_spend=True),
]
