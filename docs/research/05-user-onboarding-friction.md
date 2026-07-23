# User onboarding friction log (first real-world connection attempts)

Everything a real first user hit while connecting agents to `qnexus-mcp` v0.1.0 on
**2026-07-22**, across Windows-native **Claude Desktop** (Microsoft Store build), Windows-native
**VS Code**, and WSL-side **Claude Code**. Each entry records the symptom exactly as experienced,
the verified root cause, and its status. This is the evidence base for `../TROUBLESHOOTING.md`,
the README setup rework, and the next validation pass.

Legend — **Fixed**: resolved in this repo post-v0.1.0 · **Docs**: expected behavior that only
needed documenting · **Upstream**: bug outside this repo, worked around here · **Ops**: local
dev-loop knowledge, captured in `scripts/` comments.

## A. Server bugs the user hit (all fixed)

| # | Symptom as experienced | Root cause (verified) | Status |
|---|---|---|---|
| A1 | First tool call froze the chat **forever** (Claude Desktop and VS Code, Windows). `initialize`/`tools/list` worked, so the server looked healthy until first use | Lazy `import qnexus` (→ pandas → numpy) ran inside an anyio worker thread; numpy's C-extension DLL load deadlocks under the running ProactorEventLoop on Windows. Invisible on Linux, so CI never caught it | **Fixed** — eager SDK import in the main thread before the event loop; Windows/macOS added to CI |
| A2 | `uvx qnexus-mcp --help` printed nothing; a flag typo (`--project` for `--projects`) silently launched with **no allowlist** | `parse_known_args` + `add_help=False` swallowed anything unknown — a security flag failing open | **Fixed** — strict parsing (`parse_args`, `allow_abbrev=False`); typos exit with a usage error |
| A3 | Client showed server version **3.4.4**, muddying "which version am I on?" debugging | No `version=` passed to FastMCP, so it reported its own | **Fixed** — package version from metadata |
| A4 | ~20 lines of FastMCP banner noise in the client's log pane per launch | `server.run()` default banner on stderr | **Fixed** — `show_banner=False` |
| A5 | Cost estimation failed with `Machine name "H2-1LESC" is invalid` — even on the free default device | **Upstream qnexus 0.46 bug**: `circuits.cost` derives the syntax-checker name via `str.strip("E")` whose return value is discarded, so every non-`SC` device yields an invalid name | **Fixed here / Upstream pending** — free devices answer 0 HQC locally (nothing enqueued); billable estimates pass an explicit `syntax_checker`. Upstream report to file |
| A6 | `SyntaxWarning` noise from the SDK on Python 3.14 | Upstream qnexus 0.46 source | **Upstream** — suppressed with a filter scoped to the SDK import |

## B. Connection friction per platform (documentation gaps)

| # | Symptom as experienced | Root cause (verified) | Status |
|---|---|---|---|
| B1 | Claude Desktop: config written to `%APPDATA%\Claude\claude_desktop_config.json` was **never read**; UI kept saying "No servers added" | The **Microsoft Store (MSIX) build** virtualizes AppData: it reads `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` instead. The Settings → Developer → **Edit Config** button is the only reliable way to locate the real file | **Docs** — README + TROUBLESHOOTING |
| B2 | Claude Desktop: after fixing the path, config changes **still** seemed ignored | The app reads its config **only at cold start**, and closing the window leaves the process alive — relaunching just focuses the old instance (`second-instance: suppressing duplicate argv` in `main.log`). A full quit (tray → Quit, or `taskkill /F /IM claude.exe`) is required | **Docs** |
| B3 | Copy-pasting one client's config into another failed | Formats differ: Claude Desktop uses `{"mcpServers": {...}}` (no `type`), VS Code uses `{"servers": {... "type": "stdio"}}` | **Docs** — per-client snippets in README |
| B4 | Plain `uvx` as the command can fail in GUI-launched clients on Windows | GUI apps don't inherit the shell PATH; `%USERPROFILE%\.local\bin` may not be on it | **Docs** — recommend the absolute path to `uvx.exe` on Windows |
| B5 | "Waiting for server to respond to `initialize`…" repeated for ~40 s (first ever run: minutes) — looks exactly like a hang | Expected: first run downloads the SDK stack (pandas/pytket/numpy), and **every** start pays ~25–40 s of eager SDK import *before* the MCP handshake (the deliberate cost of fixing A1) | **Docs** — set expectations in README |
| B6 | Server shows "Failed" after it had been working | Any kill of the hosting `uv.exe`/`uvx.exe` process tree severs stdio (here: a broad `taskkill /IM uv.exe` during the dev loop). Client logs (`logs/mcp-server-<name>.log`) show `Server transport closed unexpectedly` | **Ops** — kill by PID, never by image name |

## C. Ecosystem/service behavior (documented, not fixable here)

| # | Symptom | Cause | Status |
|---|---|---|---|
| C1 | `nexus_list_jobs` intermittently returns a 500 | Nexus-side endpoint instability (observed since 2026-07-21) | **Docs** — error message already steers to by-id tools |
| C2 | `uvx qnexus-mcp` behaves differently across machines/days | Unpinned uvx resolves latest on every launch | **Docs** — pin `qnexus-mcp==X.Y.Z` (README) |
| C3 | "Why can't the agent run my circuit?" on a default install | Read-only by default is a deliberate security posture; running circuits needs `--toolsets read,execute` | **Docs** — make the opt-in prominent in every setup snippet |
| C4 | uvx warns `--reinstall` is unsupported (dev loop only) | uvx ignores the flag; it keys its cached environment on the wheel's content and refreshes automatically | **Ops** — `scripts/dev-wheel-to-windows.sh` |

## Takeaways feeding the next validation pass

1. **Real-client E2E on every OS beats unit coverage for transport-level bugs** — A1 was invisible
   to 151 passing tests and Linux CI, and fatal in every real Windows client.
2. **First-tool-call is the real smoke test** (initialize/tools-list touch no SDK code).
3. **Setup docs must be per-client and symptom-aware** — most friction was documentation debt, not code.
4. Pending upstream: qnexus `circuits.cost` checker-name bug (A5); SyntaxWarnings on 3.14 (A6).
