# qnexus-mcp

A community [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for **Quantinuum Nexus**,
wrapping the official [`qnexus`](https://github.com/Quantinuum/qnexus) Python SDK so any MCP-speaking agent
(Claude Code, Cursor, VS Code, Codex, …) can inspect Nexus and, opt-in, run circuits on the free emulator.

> **Not affiliated with, endorsed by, or an official product of Quantinuum.** "Quantinuum" and "Nexus" are
> trademarks of their respective owners, used here nominatively to describe compatibility.

<!-- mcp-name: io.github.Blite-HQ/qnexus-mcp -->

## Status

Early development. **Read-only by default.** Design and rationale live in
[`docs/DESIGN.md`](docs/DESIGN.md); the research behind it is in [`docs/research/`](docs/research/).

## Requirements

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/) (the `uvx` command). On Windows, note the
  full path to `uvx.exe` (`where uvx` in a terminal) — GUI clients don't inherit your shell PATH.
- A [Quantinuum Nexus](https://nexus.quantinuum.com) account.

## 1. Authenticate (once)

`qnexus-mcp` **never handles your Nexus token.** Authenticate out-of-band with the `qnexus` CLI
(it opens your browser):

```bash
uvx --from qnexus qnx login
```

Inside Nexus JupyterHub, authentication is automatic; do not run `qnx login` there.

## 2. Add the server to your MCP client

The launch command is the same everywhere — only the config file differs per client:

```
uvx qnexus-mcp==0.2.0                              # read-only (default)
uvx qnexus-mcp==0.2.0 --toolsets read,execute      # + run circuits on the free H2-1LE emulator
```

**Pin a version** (`==0.2.0`): `uvx` otherwise resolves the latest PyPI release on every launch —
unpinned installs are neither reproducible nor auditable. Avoid `0.1.0` on Windows: its first
tool call hangs (fixed in 0.2.0).

> **What to expect on startup:** the first ever launch downloads the quantum SDK stack (1–3 min);
> every launch takes ~30 s before the server responds — the SDK is imported up front, before the
> MCP handshake. "Waiting for server to respond to `initialize`" during that window is normal.

### Claude Desktop

Settings → Developer → Local MCP servers → **Edit Config** (always use this button — the
Microsoft Store build keeps the file under `%LOCALAPPDATA%\Packages\Claude_*\...`, **not**
`%APPDATA%\Claude`), then add:

```jsonc
{
  "mcpServers": {
    "nexus": {
      "command": "C:\\Users\\<you>\\.local\\bin\\uvx.exe", // or plain "uvx" on macOS/Linux
      "args": ["qnexus-mcp==0.2.0", "--toolsets", "read,execute"]
    }
  }
}
```

Then **quit Claude Desktop fully and reopen** — the config is only read at cold start, and
closing the window leaves the old process running (tray icon → Quit, or
`taskkill /F /IM claude.exe`).

### VS Code

Command Palette → `MCP: Open User Configuration` (or a workspace `.vscode/mcp.json`):

```jsonc
{
  "servers": {
    "nexus": {
      "type": "stdio",
      "command": "C:\\Users\\<you>\\.local\\bin\\uvx.exe", // or plain "uvx" on macOS/Linux
      "args": ["qnexus-mcp==0.2.0", "--toolsets", "read,execute"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add nexus -- uvx qnexus-mcp==0.2.0 --toolsets read,execute
```

### Other MCP clients (Cursor, Codex, …)

Same command; the config shape is one of the two JSON forms above (`mcpServers` vs
`servers` + `"type": "stdio"`) — check your client's docs for which file to put it in.

Something not working? See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — it covers every
failure mode observed in real client setups (wrong config path, slow first start, auth, rate
limits, known Nexus-side errors).

## Configuration

| Flag | Env | Default | Effect |
|---|---|---|---|
| `--toolsets` | `QNEXUS_MCP_TOOLSETS` | `read` | Capability domains to expose (`read,execute,manage,destructive`) |
| `--allow-spend` | `QNEXUS_MCP_ALLOW_SPEND` | `false` | Permit credit-spending (HQC) execution |
| `--allow-hardware` | `QNEXUS_MCP_ALLOW_HARDWARE` | `false` | Permit real-QPU targets |
| `--allow-destructive` | `QNEXUS_MCP_ALLOW_DESTRUCTIVE` | `false` | Permit delete/cancel/archive |
| `--max-credits` | `QNEXUS_MCP_MAX_CREDITS` | `0` | Hard per-call HQC ceiling; `0` blocks all spend |
| `--max-outcomes` | `QNEXUS_MCP_MAX_OUTCOMES` | `100` | Top-N cap on distinct measurement outcomes returned per result (truncation is always reported) |
| `--max-submissions-per-minute` | `QNEXUS_MCP_MAX_SUBMISSIONS_PER_MINUTE` | `6` | Sliding-window submission cap; each circuit in a batch counts as one |
| `--projects` | `QNEXUS_MCP_PROJECTS` | *(all)* | Comma-separated project allowlist, enforced on every mutating tool |

## Safety

Read-only by default. Anything that spends credits or mutates cloud state requires an explicit opt-in flag
**and** an in-protocol confirmation, and the default execution backend is the free, noiseless `H2-1LE`
emulator. Submissions are rate-limited, cloud mutations are serialized, destructive project operations
resolve their target by **exact** name (never substring), and the server never reads, stores, or returns
your Nexus token. Every control is enforced server-side; MCP tool annotations are treated as UX hints
only. See [`docs/DESIGN.md`](docs/DESIGN.md) §6–§7.

**Prompt injection (conscious design decision).** Everything Nexus returns — job names, project names,
error messages, results — is attacker-influencable content (any Nexus user can name a job) and is treated
as untrusted data. There is no structural tagging that separates "data" from "instructions" in today's MCP
ecosystem; the structural boundary here is instead that **injected content cannot escalate**: every action
with consequences (spending credits, targeting hardware, deleting anything) requires launch flags the
agent cannot set *plus* an in-protocol human confirmation naming the exact target and cost. Injected text
can at worst confuse the agent's reasoning — it cannot spend or destroy anything on its own. This residual
risk is accepted and documented, not an omission.

**Governance.** This is an early-stage, single-maintainer project (see `CODEOWNERS`): releases are
published by one person via GitHub-OIDC Trusted Publishing (no long-lived PyPI tokens). Pin a version
(above) if that trust model matters for your deployment.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Contributions are accepted under the
[Developer Certificate of Origin](https://developercertificate.org/); sign off your commits with `-s`.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
