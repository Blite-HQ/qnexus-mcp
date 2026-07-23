"""CLI entry point: eager SDK import ordering (Windows deadlock guard) and banner suppression."""

import sys
import types

from qnexus_mcp import cli


def _wire_fake_server(monkeypatch, order):
    def run(show_banner=None, **kwargs):
        order.append(("run", show_banner))

    monkeypatch.setattr(cli, "build_server", lambda config, client: types.SimpleNamespace(run=run))
    monkeypatch.setattr(cli, "QnexusClient", lambda: object())
    monkeypatch.setattr(sys, "argv", ["qnexus-mcp"])


def test_main_imports_sdk_eagerly_in_main_thread_before_run(monkeypatch):
    # Windows regression guard: importing qnexus (-> pandas -> numpy DLLs) inside an anyio
    # worker thread deadlocks under the running event loop, freezing the first tool call
    # forever. The import MUST happen in main(), before server.run() starts the loop.
    order = []
    monkeypatch.setattr(cli, "_import_sdk_eagerly", lambda: order.append("import"))
    _wire_fake_server(monkeypatch, order)
    cli.main()
    assert order[0] == "import"
    assert order[1][0] == "run"


def test_main_suppresses_the_fastmcp_banner(monkeypatch):
    # The banner is ~20 lines of stderr noise per launch in VS Code / Claude Desktop.
    order = []
    monkeypatch.setattr(cli, "_import_sdk_eagerly", lambda: None)
    _wire_fake_server(monkeypatch, order)
    cli.main()
    assert ("run", False) in order


def test_eager_import_loads_qnexus_and_pytket():
    cli._import_sdk_eagerly()
    assert "qnexus" in sys.modules
    assert "pytket.qasm" in sys.modules
