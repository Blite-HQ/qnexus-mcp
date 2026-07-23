"""Console entry point: parse config, eagerly load the SDK, build the server, run over stdio."""

from __future__ import annotations

import os
import sys
import warnings

from .client import QnexusClient
from .config import config_from_sources
from .server import build_server


def _import_sdk_eagerly() -> None:
    """Import the SDK stack in the MAIN thread, before the event loop starts.

    On Windows, importing qnexus (-> pandas -> numpy) inside an anyio worker thread deadlocks
    while numpy's C-extension DLL loads under the running ProactorEventLoop, freezing the first
    tool call forever (found live: VS Code + Claude Desktop against qnexus-mcp 0.1.0; harmless
    on Linux, so CI never saw it). Importing here costs a few seconds of startup, before the MCP
    handshake, and removes the whole class of risk -- including every lazy import site in
    client.py (`_qnx`, `_pytket_qasm`, `qnexus.exceptions`). Do NOT move these back to lazy.
    """
    with warnings.catch_warnings():
        # qnexus 0.46 emits SyntaxWarnings on Python 3.14 -- upstream noise that would land on
        # stderr (the MCP log channel). Scoped to this import only; remove when upstream fixes.
        warnings.simplefilter("ignore", SyntaxWarning)
        import pytket.qasm  # noqa: F401
        import qnexus  # noqa: F401


def main() -> None:
    # Config first: bad flags / --help fail fast without paying for the SDK import.
    config = config_from_sources(sys.argv[1:], os.environ)
    _import_sdk_eagerly()
    server = build_server(config, QnexusClient())
    # The banner is ~20 lines of stderr noise per launch in MCP clients' log panes.
    server.run(show_banner=False)
