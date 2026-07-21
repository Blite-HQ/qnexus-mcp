"""Manage tools (opt-in via `--toolsets manage`): create/upload resources (additive)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import Context

from ..context import client_of
from ..permissions import ToolSpec


async def nexus_create_project(
    ctx: Context, name: str, description: str | None = None
) -> dict[str, Any]:
    """Create (or get) a Nexus project by name."""
    return client_of(ctx).create_project(name, description)


async def nexus_upload_circuit(
    ctx: Context, circuit: str, project: str, name: str
) -> dict[str, Any]:
    """Upload an OpenQASM 2 circuit to a project for later reuse."""
    return client_of(ctx).upload_circuit(circuit, project, name)


def _spec(fn: Callable[..., Any]) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        toolset="manage",
        handler=fn,
        read_only=False,
        idempotent=False,
        description=(fn.__doc__ or "").strip().splitlines()[0],
    )


MANAGE_SPECS: list[ToolSpec] = [_spec(nexus_create_project), _spec(nexus_upload_circuit)]
