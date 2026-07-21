"""Read-only tools (always available). Each wraps one NexusClient method.

Signatures are `(ctx, <agent params>)` so FastMCP generates a correct input schema; the client is
pulled from the server state via `client_of(ctx)`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..context import client_of
from ..permissions import ToolSpec


async def nexus_auth_status(ctx: Context) -> dict[str, Any]:
    """Report whether a valid Nexus session exists."""
    return client_of(ctx).auth_status()


async def nexus_whoami(ctx: Context) -> dict[str, Any]:
    """Return the authenticated Nexus user."""
    return client_of(ctx).whoami()


async def nexus_list_devices(ctx: Context) -> list[dict[str, Any]]:
    """List available backends and their status."""
    return client_of(ctx).list_devices()


async def nexus_list_projects(ctx: Context) -> list[dict[str, Any]]:
    """List Nexus projects visible to the user."""
    return client_of(ctx).list_projects()


async def nexus_get_quota(ctx: Context) -> list[dict[str, Any]]:
    """Return remaining compilation/simulation quotas."""
    return client_of(ctx).get_quota()


async def nexus_list_jobs(
    ctx: Context, project: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """List jobs, optionally filtered by project and/or status."""
    return client_of(ctx).list_jobs(project=project, status=status)


async def nexus_job_status(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return the status of a job by id."""
    return client_of(ctx).job_status(job_id)


async def nexus_job_cost(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return the HQC cost of an existing job by id."""
    return client_of(ctx).job_cost(job_id)


async def nexus_get_results(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return counts/results for a completed job by id."""
    return client_of(ctx).get_results(job_id)


def _spec(fn: Callable[..., Any], idempotent: bool = True) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="read",
        handler=fn,
        read_only=True,
        idempotent=idempotent,
        description=(fn.__doc__ or "").strip(),
    )


READ_SPECS: list[ToolSpec] = [
    _spec(fn)
    for fn in (
        nexus_auth_status,
        nexus_whoami,
        nexus_list_devices,
        nexus_list_projects,
        nexus_get_quota,
        nexus_list_jobs,
        nexus_job_status,
        nexus_job_cost,
        nexus_get_results,
    )
]
