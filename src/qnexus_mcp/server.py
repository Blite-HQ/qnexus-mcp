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
General policy: every tool error already tells you what to do next (retry, wait, ask the human, or
stop) — read it fully before deciding your next move. Do not retry the same call in a loop; a
message that doesn't say "retry" means don't.

Auth: if you are unsure whether the user is logged in, call `nexus_auth_status` FIRST, alone, and
wait for its result before calling anything else that touches Nexus — don't fire it in parallel
with other calls, since everything else will fail identically until it's resolved. If
`logged_in` is false, tell the user to run `qnx login` in their own terminal (it opens their
browser) and stop there. Never ask the user for their Nexus username or password, and never
attempt to run `qnx login`/`qnx logout` yourself — this server never handles Nexus credentials,
by design; login is a human-initiated, out-of-band step every time.

Guard errors (spend/hardware/destructive/project) split into two kinds — tell them apart:
  - Fixable by you, no human needed: a project rejected by --projects names the allowed set
    directly in its message — retry with one of those. A "no match" / "ambiguous match" error on
    a job or project means list first (`nexus_list_jobs`/`nexus_list_projects`) and retry with a
    corrected, exact name or id — never guess.
  - Requires the human, don't retry: "--allow-spend" / "--allow-hardware" / "--allow-destructive"
    / quota-exhausted errors mean the *server* was launched without that capability — you cannot
    enable it yourself. Explain this plainly and stop; only the human can restart the server with
    different flags. Likewise, if the user declines an in-protocol confirmation (spend or
    destructive), treat that as their answer — do not immediately re-prompt.

Known-flaky endpoint: `nexus_list_jobs` occasionally returns a Nexus-side server error unrelated
to your request. If it fails, use `nexus_job_status`/`nexus_get_results` by id instead of retrying
the list.

Submissions are not truly idempotent (the name tag is cosmetic). If a submit's outcome is unclear
— e.g. the call itself timed out — check `nexus_list_jobs`/`nexus_job_status` before resubmitting,
to avoid an unintended duplicate job or double-spend.

Typical flow to run a circuit: `nexus_auth_status` -> `nexus_list_devices` (or just use the free
default) -> `nexus_estimate_cost` -> `nexus_submit` (or `nexus_submit_and_wait` for short jobs;
prefer plain `nexus_submit` + polling `nexus_job_status` for anything that might run long) ->
`nexus_get_results` once status is COMPLETED. All of read/execute default to the free, noiseless
`H2-1LE` emulator unless you name a different device.
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
