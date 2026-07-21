# qnexus-mcp

A community [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for **Quantinuum Nexus**,
wrapping the official [`qnexus`](https://github.com/Quantinuum/qnexus) Python SDK so any MCP-speaking agent
(Claude Code, Cursor, VS Code, Codex, …) can inspect Nexus and — opt-in — run circuits on the free emulator.

> **Not affiliated with, endorsed by, or an official product of Quantinuum.** "Quantinuum" and "Nexus" are
> trademarks of their respective owners, used here nominatively to describe compatibility.

<!-- mcp-name: io.github.Blite-HQ/qnexus-mcp -->

## Status

Early development. **Read-only by default.** Design and rationale live in
[`docs/DESIGN.md`](docs/DESIGN.md); the research behind it is in [`docs/research/`](docs/research/).

## Install & run

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uvx qnexus-mcp
```

## Authenticate (once)

`qnexus-mcp` **never handles your Nexus token.** Authenticate out-of-band with the `qnexus` CLI:

```bash
qnx login
```

Inside Nexus JupyterHub, authentication is automatic — do not run `qnx login` there.

## Configure your MCP client

Add to your client's MCP config (Claude Code / Cursor / VS Code share this shape). Default is **read-only**:

```jsonc
{
  "mcpServers": {
    "nexus": { "command": "uvx", "args": ["qnexus-mcp"] }
  }
}
```

To also allow running circuits (defaults to the free `H2-1LE` emulator):

```jsonc
{
  "mcpServers": {
    "nexus": { "command": "uvx", "args": ["qnexus-mcp", "--toolsets", "read,execute"] }
  }
}
```

## Configuration

| Flag | Env | Default | Effect |
|---|---|---|---|
| `--toolsets` | `QNEXUS_MCP_TOOLSETS` | `read` | Capability domains to expose (`read,execute,manage,destructive`) |
| `--allow-spend` | `QNEXUS_MCP_ALLOW_SPEND` | `false` | Permit credit-spending (HQC) execution |
| `--allow-hardware` | `QNEXUS_MCP_ALLOW_HARDWARE` | `false` | Permit real-QPU targets |
| `--allow-destructive` | `QNEXUS_MCP_ALLOW_DESTRUCTIVE` | `false` | Permit delete/cancel/archive |
| `--max-credits` | `QNEXUS_MCP_MAX_CREDITS` | `0` | Hard per-call HQC ceiling; `0` blocks all spend |
| `--projects` | `QNEXUS_MCP_PROJECTS` | *(all)* | Comma-separated project allowlist, enforced on every mutating tool |

## Safety

Read-only by default. Anything that spends credits or mutates cloud state requires an explicit opt-in flag
**and** an in-protocol confirmation, and the default execution backend is the free, noiseless `H2-1LE`
emulator. Submissions are rate-limited, cloud mutations are serialized, destructive project operations
resolve their target by **exact** name (never substring), and the server never reads, stores, or returns
your Nexus token. Every control is enforced server-side; MCP tool annotations are treated as UX hints
only. See [`docs/DESIGN.md`](docs/DESIGN.md) §6–§7.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Contributions are accepted under the
[Developer Certificate of Origin](https://developercertificate.org/) — sign off your commits with `-s`.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
