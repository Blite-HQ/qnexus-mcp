"""Manage tools (opt-in via `--toolsets manage`): create/upload resources (additive)."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..context import call_sync, client_of, config_of, mutation_lock_of
from ..guards import check_project_allowed
from ..permissions import ToolSpec


async def nexus_create_project(
    ctx: Context, name: str, description: str | None = None
) -> dict[str, Any]:
    """Create (or get) a Nexus project by name."""
    check_project_allowed(config_of(ctx), name)
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).create_project, name, description)


async def nexus_upload_circuit(
    ctx: Context, circuit: str, project: str, name: str
) -> dict[str, Any]:
    """Upload an OpenQASM 2 circuit to a project for later reuse."""
    check_project_allowed(config_of(ctx), project)
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).upload_circuit, circuit, project, name)


async def nexus_upload_program(
    ctx: Context, program_base64: str, project: str, name: str
) -> dict[str, Any]:
    """Upload a QIR program (base64-encoded bitcode, max 5 MiB) to a project."""
    check_project_allowed(config_of(ctx), project)
    async with mutation_lock_of(ctx):
        return await call_sync(client_of(ctx).upload_program, program_base64, project, name)


def _spec(fn: Callable[..., Any]) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="manage",
        handler=fn,
        read_only=False,
        idempotent=False,
        description=inspect.cleandoc(fn.__doc__ or ""),
    )


MANAGE_SPECS: list[ToolSpec] = [
    _spec(nexus_create_project),
    _spec(nexus_upload_circuit),
    _spec(nexus_upload_program),
]
