"""Bind per-server state (client + config) and read it back inside a tool via its Context.

FastMCP generates each tool's input schema from its signature, so tools must NOT take `client`/
`config` as parameters. Instead we stash them on the server instance at build time and read them
back through `ctx.fastmcp` at call time. This keeps handler signatures clean (agent params + ctx).
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from .client import NexusClient
from .config import ServerConfig
from .guards import Confirm

_CLIENT_ATTR = "_qnexus_mcp_client"
_CONFIG_ATTR = "_qnexus_mcp_config"


def bind_state(server: Any, client: NexusClient, config: ServerConfig) -> None:
    setattr(server, _CLIENT_ATTR, client)
    setattr(server, _CONFIG_ATTR, config)


def client_of(ctx: Context) -> NexusClient:
    client: NexusClient = getattr(ctx.fastmcp, _CLIENT_ATTR)
    return client


def config_of(ctx: Context) -> ServerConfig:
    config: ServerConfig = getattr(ctx.fastmcp, _CONFIG_ATTR)
    return config


def confirm_from_ctx(ctx: Context) -> Confirm:
    """Build a yes/no confirmation callback backed by the MCP client's elicitation."""

    async def confirm(message: str) -> bool:
        # response_type=bool is valid at runtime; mypy mis-resolves elicit's overloaded signature.
        result = await ctx.elicit(message, response_type=bool)  # type: ignore[arg-type]
        return getattr(result, "action", None) == "accept" and bool(getattr(result, "data", False))

    return confirm
