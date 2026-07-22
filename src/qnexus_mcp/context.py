"""Bind per-server state (client + config + guards) and read it back inside a tool via its Context.

FastMCP generates each tool's input schema from its signature, so tools must NOT take `client`/
`config` as parameters. Instead we stash them on the server instance at build time and read them
back through `ctx.fastmcp` at call time. This keeps handler signatures clean (agent params + ctx).
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import anyio
import anyio.to_thread
from fastmcp import Context

from .client import NexusClient
from .config import ServerConfig
from .guards import Confirm, SubmitRateLimiter

_CLIENT_ATTR = "_qnexus_mcp_client"
_CONFIG_ATTR = "_qnexus_mcp_config"
_LOCK_ATTR = "_qnexus_mcp_mutation_lock"
_RATE_ATTR = "_qnexus_mcp_rate_limiter"

T = TypeVar("T")


def bind_state(server: Any, client: NexusClient, config: ServerConfig) -> None:
    setattr(server, _CLIENT_ATTR, client)
    setattr(server, _CONFIG_ATTR, config)
    setattr(server, _LOCK_ATTR, anyio.Lock())
    setattr(server, _RATE_ATTR, SubmitRateLimiter())


def client_of(ctx: Context) -> NexusClient:
    client: NexusClient = getattr(ctx.fastmcp, _CLIENT_ATTR)
    return client


def config_of(ctx: Context) -> ServerConfig:
    config: ServerConfig = getattr(ctx.fastmcp, _CONFIG_ATTR)
    return config


def mutation_lock_of(ctx: Context) -> anyio.Lock:
    """One lock per server: mutating tools hold it so cloud mutations are serialized (DESIGN §7)."""
    lock: anyio.Lock = getattr(ctx.fastmcp, _LOCK_ATTR)
    return lock


def rate_limiter_of(ctx: Context) -> SubmitRateLimiter:
    limiter: SubmitRateLimiter = getattr(ctx.fastmcp, _RATE_ATTR)
    return limiter


async def call_sync(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking NexusClient call in a worker thread.

    Every qnexus call is synchronous (blocking httpx), and `qnx.jobs.wait_for` even runs its own
    `asyncio.run()`, which raises RuntimeError if invoked on a running event loop. Offloading to a
    thread keeps the server responsive during long waits and gives the SDK a loop-free thread.
    """
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def confirm_from_ctx(ctx: Context) -> Confirm:
    """Build a yes/no confirmation callback backed by the MCP client's elicitation."""

    async def confirm(message: str) -> bool:
        # response_type=bool is valid at runtime; mypy mis-resolves elicit's overloaded signature.
        result = await ctx.elicit(message, response_type=bool)  # type: ignore[arg-type]
        return getattr(result, "action", None) == "accept" and bool(getattr(result, "data", False))

    return confirm
