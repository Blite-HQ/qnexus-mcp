"""Destructive tools (opt-in via `--toolsets destructive` AND `--allow-destructive`).

Every tool requires an in-protocol confirmation naming the exact target before executing. Project
targets are resolved by EXACT name match server-side (never substring); an ambiguous or missing
name aborts with a clear error instead of acting.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..context import call_sync, client_of, config_of, confirm_from_ctx, mutation_lock_of
from ..guards import ConfirmationDenied, check_project_allowed
from ..permissions import ToolSpec


async def _require_confirmation(ctx: Context, message: str) -> None:
    if not await confirm_from_ctx(ctx)(message):
        raise ConfirmationDenied("destructive action was not confirmed by the user")


async def nexus_cancel_job(ctx: Context, job_id: str) -> dict[str, Any]:
    """Cancel a running or queued job on Nexus."""
    await _require_confirmation(ctx, f"Cancel job {job_id}? This stops it on Nexus.")
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).cancel_job, job_id)


async def nexus_delete_job(ctx: Context, job_id: str) -> dict[str, Any]:
    """Delete a job and its data. Irreversible."""
    await _require_confirmation(ctx, f"Delete job {job_id}? This is irreversible.")
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).delete_job, job_id)


async def nexus_archive_project(ctx: Context, name: str) -> dict[str, Any]:
    """Archive a project by exact name (reversible; required before deletion)."""
    check_project_allowed(config_of(ctx), name)
    await _require_confirmation(ctx, f"Archive project '{name}'?")
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).archive_project, name)


async def nexus_delete_project(ctx: Context, name: str) -> dict[str, Any]:
    """Delete a project (by exact name) and ALL its data. Irreversible; archive it first."""
    check_project_allowed(config_of(ctx), name)
    await _require_confirmation(
        ctx, f"Delete project '{name}' and ALL its data? This is irreversible."
    )
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).delete_project, name)


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
