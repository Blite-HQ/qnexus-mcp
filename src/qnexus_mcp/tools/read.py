"""Read-only tools (always available). Each wraps one NexusClient method.

Signatures are `(ctx, <agent params>)` so FastMCP generates a correct input schema; the client is
pulled from the server state via `client_of(ctx)` and every (blocking) client call runs in a worker
thread via `call_sync`.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..context import call_sync, client_of, config_of
from ..permissions import ToolSpec
from ..results import shape_result

# Bound list-page sizes so an account with a long history can never produce an unbounded response.
Limit = Annotated[int, Field(ge=1, le=500)]


async def nexus_auth_status(ctx: Context) -> dict[str, Any]:
    """Report whether a valid Nexus session exists."""
    return await call_sync(client_of(ctx).auth_status)


async def nexus_whoami(ctx: Context) -> dict[str, Any]:
    """Return the authenticated Nexus user."""
    return await call_sync(client_of(ctx).whoami)


async def nexus_list_devices(ctx: Context) -> list[dict[str, Any]]:
    """List available backends and their status."""
    return await call_sync(client_of(ctx).list_devices)


async def nexus_device_status(ctx: Context, device: str) -> dict[str, Any]:
    """Report whether a device is online. Emulators/syntax checkers are always available."""
    return await call_sync(client_of(ctx).device_status, device)


async def nexus_list_projects(
    ctx: Context, limit: Limit = 50, name_like: str | None = None, archived: bool = False
) -> dict[str, Any]:
    """List Nexus projects visible to the user (one page of up to `limit`, plus the total count).

    Optional `name_like` substring filter; set `archived` to list archived projects instead.
    """
    return await call_sync(
        client_of(ctx).list_projects, limit=limit, name_like=name_like, archived=archived
    )


async def nexus_get_quota(ctx: Context) -> list[dict[str, Any]]:
    """Return remaining compilation/simulation quotas."""
    return await call_sync(client_of(ctx).get_quota)


async def nexus_list_jobs(
    ctx: Context,
    limit: Limit = 50,
    project: str | None = None,
    status: str | None = None,
    name_like: str | None = None,
) -> dict[str, Any]:
    """List jobs visible to the user (one page of up to `limit`, plus the total count).

    Optional filters: exact `project` name, `status` (e.g. COMPLETED, RUNNING, ERROR), and a
    `name_like` substring. Occasionally returns a Nexus-side server error unrelated to your
    request; if so, use nexus_job_status / nexus_get_results by id instead of retrying this call.
    """
    return await call_sync(
        client_of(ctx).list_jobs, limit=limit, project=project, status=status, name_like=name_like
    )


async def nexus_job_status(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return the status of a job by id."""
    return await call_sync(client_of(ctx).job_status, job_id)


async def nexus_job_cost(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return the HQC cost of an existing job by id."""
    return await call_sync(client_of(ctx).job_cost, job_id)


async def nexus_get_results(ctx: Context, job_id: str) -> dict[str, Any]:
    """Return measurement counts for a completed job by id.

    Counts are capped at the top --max-outcomes outcomes by frequency; total_outcomes /
    omitted_outcomes / omitted_shots report any truncation. Multi-circuit (batch) jobs return
    one entry per circuit under `items`, in submission order.
    """
    raw = await call_sync(client_of(ctx).get_results, job_id)
    return shape_result(job_id, raw["counts_list"], config_of(ctx).max_outcomes)


def _spec(fn: Callable[..., Any], idempotent: bool = True) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="read",
        handler=fn,
        read_only=True,
        idempotent=idempotent,
        description=inspect.cleandoc(fn.__doc__ or ""),
    )


READ_SPECS: list[ToolSpec] = [
    _spec(fn)
    for fn in (
        nexus_auth_status,
        nexus_whoami,
        nexus_list_devices,
        nexus_device_status,
        nexus_list_projects,
        nexus_get_quota,
        nexus_list_jobs,
        nexus_job_status,
        nexus_job_cost,
        nexus_get_results,
    )
]
