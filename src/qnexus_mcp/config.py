"""Launch configuration: the two-axis permission gates, parsed from argv/env."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_TOOLSETS = frozenset({"read", "execute", "manage", "destructive"})
DEFAULT_TOOLSETS = frozenset({"read"})
DEFAULT_PROJECT = "qnexus-mcp"  # project used when a tool call names none


class ServerConfig(BaseModel):
    """Immutable server configuration. Defaults are read-only strict."""

    model_config = ConfigDict(frozen=True)

    toolsets: frozenset[str] = DEFAULT_TOOLSETS
    allow_spend: bool = False
    allow_hardware: bool = False
    allow_destructive: bool = False
    max_credits: float = Field(default=0.0, ge=0.0)
    # Cap on distinct measurement outcomes returned per result item (top-N by frequency), so a
    # noisy/many-qubit job can never flood the agent's context. Truncation is always reported.
    max_outcomes: int = Field(default=100, ge=1)
    # Sliding-window cap on circuit submissions per minute (a batch of N consumes N slots).
    max_submissions_per_minute: int = Field(default=6, ge=1)
    # Project allowlist for every mutating tool (execute/manage/destructive). None = all allowed.
    # Enforced by guards.check_project_allowed; reads are unaffected.
    projects: frozenset[str] | None = None

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


def _int_from(cli: int | None, env: Mapping[str, str], key: str, default: int) -> int:
    """Resolve an integer setting: CLI wins, then env (with a clear parse error), then default."""
    if cli is not None:
        return cli
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc


def config_from_sources(argv: list[str], env: Mapping[str, str]) -> ServerConfig:
    """Build a ServerConfig from CLI args (highest priority) then env vars.

    Parsing is STRICT: an unknown flag exits with a usage error instead of being silently
    dropped. Found live on Windows: with parse_known_args, the typo `--project sandbox`
    launched the server with NO allowlist at all -- a security flag failing open. --help works
    (the process exits before any MCP handshake, so stdout is not yet the protocol channel).
    """
    # allow_abbrev=False: no implicit prefix matching either -- an abbreviation could silently
    # bind to a different flag as new flags get added. Exact flags only.
    p = argparse.ArgumentParser(
        prog="qnexus-mcp",
        description="MCP server for Quantinuum Nexus",
        allow_abbrev=False,
    )
    p.add_argument("--toolsets")
    p.add_argument("--allow-spend", action="store_true", default=None)
    p.add_argument("--allow-hardware", action="store_true", default=None)
    p.add_argument("--allow-destructive", action="store_true", default=None)
    p.add_argument("--max-credits", type=float)
    p.add_argument("--max-outcomes", type=int)
    p.add_argument("--max-submissions-per-minute", type=int)
    p.add_argument("--projects")
    args = p.parse_args(argv)

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

    projects = _split(args.projects) or _split(env.get("QNEXUS_MCP_PROJECTS"))

    return ServerConfig(
        toolsets=toolsets,
        allow_spend=flag(args.allow_spend, "QNEXUS_MCP_ALLOW_SPEND", False),
        allow_hardware=flag(args.allow_hardware, "QNEXUS_MCP_ALLOW_HARDWARE", False),
        allow_destructive=flag(args.allow_destructive, "QNEXUS_MCP_ALLOW_DESTRUCTIVE", False),
        max_credits=max_credits,
        max_outcomes=_int_from(args.max_outcomes, env, "QNEXUS_MCP_MAX_OUTCOMES", 100),
        max_submissions_per_minute=_int_from(
            args.max_submissions_per_minute, env, "QNEXUS_MCP_MAX_SUBMISSIONS_PER_MINUTE", 6
        ),
        projects=projects,
    )
