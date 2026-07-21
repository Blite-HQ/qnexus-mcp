"""Destructive tools (opt-in via `--toolsets destructive` AND `--allow-destructive`).

Every tool requires an in-protocol confirmation naming the exact target before executing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..context import client_of, confirm_from_ctx
from ..guards import ConfirmationDenied
from ..permissions import ToolSpec


async def _require_confirmation(ctx: Context, message: str) -> None:
    if not await confirm_from_ctx(ctx)(message):
        raise ConfirmationDenied("destructive action was not confirmed by the user")


async def nexus_cancel_job(ctx: Context, job_id: str) -> dict[str, Any]:
    """Cancel a running or queued job on Nexus."""
    await _require_confirmation(ctx, f"Cancel job {job_id}? This stops it on Nexus.")
    return client_of(ctx).cancel_job(job_id)


async def nexus_delete_job(ctx: Context, job_id: str) -> dict[str, Any]:
    """Delete a job and its data. Irreversible."""
    await _require_confirmation(ctx, f"Delete job {job_id}? This is irreversible.")
    return client_of(ctx).delete_job(job_id)


async def nexus_archive_project(ctx: Context, name: str) -> dict[str, Any]:
    """Archive a project (reversible; required before deletion)."""
    await _require_confirmation(ctx, f"Archive project '{name}'?")
    return client_of(ctx).archive_project(name)


async def nexus_delete_project(ctx: Context, name: str) -> dict[str, Any]:
    """Delete a project and ALL its data. Irreversible; the project must be archived first."""
    await _require_confirmation(
        ctx, f"Delete project '{name}' and ALL its data? This is irreversible."
    )
    return client_of(ctx).delete_project(name)


def _spec(fn: Callable[..., Any]) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="destructive",
        handler=fn,
        read_only=False,
        idempotent=False,
        is_destructive=True,
        description=(fn.__doc__ or "").strip().splitlines()[0],
    )


DESTRUCTIVE_SPECS: list[ToolSpec] = [
    _spec(nexus_cancel_job),
    _spec(nexus_delete_job),
    _spec(nexus_archive_project),
    _spec(nexus_delete_project),
]
