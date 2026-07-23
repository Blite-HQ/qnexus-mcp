# Troubleshooting

Symptom-first guide, built from real first-user connection attempts (the full log lives in
[`research/05-user-onboarding-friction.md`](research/05-user-onboarding-friction.md)). Find your
symptom, apply the fix.

## Startup

### "Waiting for server to respond to `initialize`…" repeats — is it hung?

Almost certainly not. Two normal delays stack up:

- **First ever run**: `uvx` downloads the quantum SDK stack (pandas, pytket, numpy) — 1–3 minutes
  depending on your connection.
- **Every run**: ~25–40 s of SDK import *before* the server answers the MCP handshake. This is
  deliberate: importing lazily inside a worker thread deadlocks on Windows (see below), so the
  import happens up front.

Give it two minutes before assuming failure. If it still hasn't answered, check the logs
([below](#where-are-the-logs)).

### The first tool call freezes the chat forever (Windows)

You are running **v0.1.0**, which has a Windows-only import deadlock: `initialize` and
`tools/list` work, then the first real tool call hangs indefinitely. Upgrade the pin to
**v0.2.0 or later** — the versions with the fix.

### `uvx` / `uvx.exe` "not found" when the client starts the server

GUI apps on Windows don't inherit your shell's PATH. Use the **absolute path** in the config,
e.g. `"command": "C:\\Users\\<you>\\.local\\bin\\uvx.exe"`. (Find yours with `where uvx` in a
terminal.)

## Client configuration

### Claude Desktop shows "No servers added" even though I edited the config

Two traps, both common:

1. **Wrong file (Microsoft Store build).** The Store (MSIX) build does *not* read
   `%APPDATA%\Claude\claude_desktop_config.json`. Its real config lives under
   `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\`. Don't hunt for it — use
   **Settings → Developer → Edit Config**, which always opens the file the app actually reads.
2. **The app never actually restarted.** Claude Desktop reads its config **only at cold start**,
   and closing the window leaves the process alive in the tray — reopening just focuses the old
   instance. Fully quit (tray icon → Quit, or `taskkill /F /IM claude.exe`) and reopen.

### My config works in one client but not another

The JSON shape differs per client (same command in both):

```jsonc
// Claude Desktop (claude_desktop_config.json)
{ "mcpServers": { "nexus": { "command": "...", "args": ["..."] } } }

// VS Code (mcp.json)
{ "servers": { "nexus": { "type": "stdio", "command": "...", "args": ["..."] } } }
```

### The server shows "Failed" / "Server disconnected" after working fine

The hosting process died — the client log will say `Server transport closed unexpectedly`.
Common causes: something killed `uv.exe`/`uvx.exe` (task managers, dev scripts), or the machine
slept mid-session. Restart the server from the client (Claude Desktop: full quit + reopen).

## Using the tools

### `logged_in: false` / "Not authenticated with Nexus"

Run `qnx login` yourself in a terminal (it opens your browser). The server never handles your
Nexus credentials, by design — no tool can log you in, and the agent should never ask for your
password. Inside Nexus JupyterHub, auth is automatic; don't run `qnx login` there.

### "The agent says it can't submit / the submit tool doesn't exist"

Default is **read-only**. Running circuits is an explicit opt-in at launch:
`--toolsets read,execute` (free `H2-1LE` emulator by default). Billable devices additionally
need `--allow-spend` (and `--allow-hardware` for real QPUs) — these can never be enabled from a
tool call.

### `nexus_list_jobs` returns a Nexus server error (500)

Known **Nexus-side** endpoint instability, not an MCP problem. Don't retry in a loop; use
`nexus_job_status` / `nexus_get_results` by job id instead.

### "Rate limit: at most N submissions per minute"

Working as designed (each circuit of a batch counts as one submission). Wait, or relaunch with a
higher `--max-submissions-per-minute`. A batch larger than the cap is rejected immediately with
guidance to split it — waiting will not help that case.

### Cost estimation fails with `Machine name "H2-1LESC" is invalid`

Upstream `qnexus` 0.46 bug in checker-name derivation, worked around in qnexus-mcp **v0.2.0+**
(free devices answer 0 HQC locally; billable estimates pass an explicit checker). Upgrade your pin.

## Where are the logs?

| Client | Location |
|---|---|
| Claude Desktop | `logs/mcp-server-<name>.log` next to `claude_desktop_config.json` (Store build: under `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\logs\`) |
| VS Code | Output panel → `MCP: <name>` |
| Claude Code | `claude mcp list` for status; run with `claude --debug` for transport detail |

The server itself logs to **stderr** (never stdout — that's the protocol channel), so everything
it prints appears in these client logs.
