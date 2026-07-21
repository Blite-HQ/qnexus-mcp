"""Build the FastMCP server: register only the tools the launch config permits."""

from __future__ import annotations

import anyio
from fastmcp import FastMCP
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from .client import NexusClient
from .config import ServerConfig
from .context import bind_state
from .permissions import annotations_for, select_tools
from .tools import ALL_SPECS


def build_server(config: ServerConfig, client: NexusClient) -> FastMCP:
    server = FastMCP("qnexus-mcp", mask_error_details=True)
    bind_state(server, client, config)
    for spec in select_tools(ALL_SPECS, config):
        a = annotations_for(spec)
        tool = Tool.from_function(
            spec.handler,
            name=spec.name,
            description=spec.description,
            annotations=ToolAnnotations(
                readOnlyHint=a["readOnlyHint"],
                destructiveHint=a["destructiveHint"],
                idempotentHint=a["idempotentHint"],
                openWorldHint=a["openWorldHint"],
            ),
        )
        server.add_tool(tool)
    return server


def registered_tool_names(server: FastMCP) -> set[str]:
    tools = anyio.run(server.list_tools)
    return {tool.name for tool in tools}
