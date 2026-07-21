"""Launch configuration: the two-axis permission gates, parsed from argv/env."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_TOOLSETS = frozenset({"read", "execute", "manage", "destructive"})
DEFAULT_TOOLSETS = frozenset({"read"})


class ServerConfig(BaseModel):
    """Immutable server configuration. Defaults are read-only strict."""

    model_config = ConfigDict(frozen=True)

    toolsets: frozenset[str] = DEFAULT_TOOLSETS
    allow_spend: bool = False
    allow_hardware: bool = False
    allow_destructive: bool = False
    max_credits: float = Field(default=0.0, ge=0.0)
    projects: tuple[str, ...] | None = None  # reserved; enforcement not yet wired

    @field_validator("toolsets")
    @classmethod
    def _known_toolsets(cls, v: frozenset[str]) -> frozenset[str]:
        unknown = v - VALID_TOOLSETS
        if unknown:
            raise ValueError(f"unknown toolsets: {sorted(unknown)}")
        return v


def _split(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def config_from_sources(argv: list[str], env: Mapping[str, str]) -> ServerConfig:
    """Build a ServerConfig from CLI args (highest priority) then env vars."""
    p = argparse.ArgumentParser(prog="qnexus-mcp", add_help=False)
    p.add_argument("--toolsets")
    p.add_argument("--allow-spend", action="store_true", default=None)
    p.add_argument("--allow-hardware", action="store_true", default=None)
    p.add_argument("--allow-destructive", action="store_true", default=None)
    p.add_argument("--max-credits", type=float)
    args, _ = p.parse_known_args(argv)

    def flag(cli: bool | None, key: str, default: bool) -> bool:
        if cli is not None:
            return cli
        if key in env:
            return env[key].lower() in {"1", "true", "yes"}
        return default

    # read is always on: union the selection with the default so it can never be dropped.
    selected = _split(args.toolsets) or _split(env.get("QNEXUS_MCP_TOOLSETS")) or DEFAULT_TOOLSETS
    toolsets = selected | DEFAULT_TOOLSETS

    max_credits = args.max_credits
    if max_credits is None:
        raw = env.get("QNEXUS_MCP_MAX_CREDITS", "0")
        try:
            max_credits = float(raw)
        except ValueError as exc:
            raise ValueError(f"QNEXUS_MCP_MAX_CREDITS must be a number, got {raw!r}") from exc

    return ServerConfig(
        toolsets=toolsets,
        allow_spend=flag(args.allow_spend, "QNEXUS_MCP_ALLOW_SPEND", False),
        allow_hardware=flag(args.allow_hardware, "QNEXUS_MCP_ALLOW_HARDWARE", False),
        allow_destructive=flag(args.allow_destructive, "QNEXUS_MCP_ALLOW_DESTRUCTIVE", False),
        max_credits=max_credits,
    )
