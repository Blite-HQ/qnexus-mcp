"""The tool registry and server-side gating (register-time omission)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import ServerConfig


@dataclass(frozen=True)
class ToolSpec:
    name: str
    toolset: str
    handler: Callable[..., Any]
    read_only: bool = False
    idempotent: bool = False
    is_spend: bool = False
    is_destructive: bool = False
    is_hardware: bool = False
    description: str = ""


def is_tool_allowed(spec: ToolSpec, config: ServerConfig) -> bool:
    # Registration gate: toolset membership + inherent destructiveness. Spend/hardware
    # severity is per-CALL (the same submit tool serves free H2-1LE and billable devices),
    # so it is enforced at runtime by SpendGuard, never by hiding the tool. `is_spend`/
    # `is_hardware` on a ToolSpec remain as honest metadata, not registration gates.
    if spec.toolset not in config.toolsets:
        return False
    if spec.is_destructive and not config.allow_destructive:
        return False
    return True


def select_tools(specs: list[ToolSpec], config: ServerConfig) -> list[ToolSpec]:
    return [s for s in specs if is_tool_allowed(s, config)]


def annotations_for(spec: ToolSpec) -> dict[str, bool]:
    return {
        "readOnlyHint": spec.read_only,
        "destructiveHint": spec.is_destructive,
        "idempotentHint": spec.idempotent,
        "openWorldHint": True,  # every tool talks to the Nexus cloud
    }
