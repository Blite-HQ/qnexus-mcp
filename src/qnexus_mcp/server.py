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

_INSTRUCTIONS = """\
Before calling any other tool, check `nexus_auth_status` if you are unsure whether the user is
logged in. If `logged_in` is false: tell the user to run `qnx login` in their own terminal (it
opens their browser) and stop there. Do not ask the user for their Nexus username or password,
and do not attempt to run `qnx login`/`qnx logout` yourself — this server never handles Nexus
credentials, by design; login is a human-initiated, out-of-band step every time.
"""


def build_server(config: ServerConfig, client: NexusClient) -> FastMCP:
    server = FastMCP("qnexus-mcp", instructions=_INSTRUCTIONS, mask_error_details=True)
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
