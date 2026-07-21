# qnexus-mcp — Design

**Status:** FROZEN v1 (design) · **Date:** 2026-07-20 · **Authors:** Dylan Chaves Hernández + Claude (Opus 4.8)

> An independent, community-built [Model Context Protocol](https://modelcontextprotocol.io) server that
> exposes the [Quantinuum Nexus](https://docs.quantinuum.com/nexus/) quantum-computing cloud to LLM
> agents, by wrapping the official [`qnexus`](https://github.com/Quantinuum/qnexus) Python SDK.
>
> **Not affiliated with, endorsed by, or an official product of Quantinuum.** "Quantinuum" and "Nexus"
> are trademarks of their owner and are used here only nominatively, to describe compatibility.

---

## 1. Summary & vision

There is **no official MCP server for Quantinuum Nexus** (verified 2026-07-20 against Quantinuum/CQCL
repos and docs). `qnexus-mcp` fills that gap with a **reference-quality** server: an LLM agent (Claude
Code, Cursor, VS Code, …) can inspect Nexus projects, devices, jobs, quotas and results, and — when
explicitly permitted — compile and run circuits on the H-series emulators, all through a small, audited,
safe-by-default tool surface.

The ambition is that the project is good enough that **Quantinuum adopts or co-maintains it**. That is
earned, not stamped (see §14): we build to first-party quality, publish under a community namespace,
gain traction (including use during the Quantathon), and *then* propose adoption. The namespace mechanics
make the handoff a single mechanical step.

**Design north stars**

1. **Safe by default.** The default posture is *read-only*. Nothing runs, spends, or mutates without an
   explicit, per-capability opt-in. Money- and state-changing actions are enforced **server-side**, never
   left to the LLM or the client.
2. **In-protocol confirmation is the differentiator.** Every credit-spending or destructive action does a
   cost/target estimate → an MCP `elicitation` confirmation → then executes, refusing above a ceiling.
   Published official MCP servers typically only *recommend* human confirmation in their docs;
   `qnexus-mcp` enforces it inside the protocol itself.
3. **Adoptable.** License, toolchain, governance and packaging mirror or exceed Quantinuum's own repos, so
   the codebase reads as first-party and re-namespacing to `com.quantinuum.*` is trivial.

## 2. Non-goals

- **No team / role / credential management.** Near-zero legitimate agent use-case, large blast radius
  (`qnexus` "credentials" are saved *third-party provider* secrets — IBMQ/Braket/Quantinuum logins). A
  read-only `whoami` is the only identity surface exposed.
- **No remote/HTTP transport in v1.** stdio only. A hosted OAuth 2.1 variant is a clean future add-on
  (§5) — the local design must not make it hard, but it is out of scope now.
- **No token handling of our own.** Auth is delegated entirely to `qnexus` (§5).
- **No 1:1 CRUD mirror of the SDK.** We expose consolidated, workflow-level tools (auto-generating
  flat tools from an API surface, with no read/write/cost awareness, is the anti-pattern).

## 3. Architecture

```
LLM client (Claude Code / Cursor / VS Code)
        │  MCP over stdio (JSON-RPC)
        ▼
qnexus-mcp  ── FastMCP 2.0 server (Python)
        │  in-process calls
        ▼
qnexus  ── official Python SDK  ──HTTPS──▶  Nexus cloud (projects, devices, jobs, quotas)
```

- **Language / runtime:** Python 3.10–3.13 (matches `qnexus`/`pytket`), managed with `uv`.
- **Framework:** [FastMCP](https://github.com/jlowin/fastmcp) (2.x API surface; currently pinned to 3.x).
  Chosen because we wrap a Python SDK and it provides, out of the box: `ToolAnnotations`, `ctx.elicit()`
  confirmation gates, structured output, `ToolError` + `mask_error_details`, and stdio + HTTP transports —
  letting us implement per-toolset gating declaratively in Python.
- **Transport: stdio** — *standard input/output*, the local MCP transport: the client launches `qnexus-mcp`
  as a child process and the two exchange JSON-RPC over `stdin`/`stdout` (a pipe between two programs). It is
  **not** a network service and **not** a "studio" app. The only other MCP transport is HTTP, reserved for a
  possible future hosted variant (§5). One server process per user, launched by their MCP client, so it runs
  *as the user* and reads *their* qnexus token cache — no shared server, no shared credentials, no hosting.
- **Client-agnostic, zero coupling:** any MCP-speaking agent can consume this server — Claude Code, Codex,
  VS Code, Cursor, or an in-house agent. `qnexus-mcp` has **no dependency on any other project**; its only
  possible integration relationship is the inverse — another project (e.g. a larger agent platform) can *add*
  this server as one of its MCP servers, exactly as any client would.

## 4. Tool catalog

Consolidated, `snake_case`, `nexus_` prefix, workflow-level. Class: **R**=read · **W**=write/additive ·
**$**=spends credits (HQC) · **X**=destructive. `MCP` = tool annotations (hints only; see §6/§7).

| Toolset | Tool | Class | MCP annotations |
|---|---|---|---|
| **read** *(always on)* | `nexus_auth_status` | R | readOnly, idempotent, openWorld |
| | `nexus_whoami` | R | readOnly, idempotent, openWorld |
| | `nexus_list_projects` | R | readOnly, idempotent, openWorld |
| | `nexus_list_devices` | R | readOnly, idempotent, openWorld |
| | `nexus_device_status` | R | readOnly, idempotent, openWorld |
| | `nexus_get_quota` | R | readOnly, idempotent, openWorld |
| | `nexus_list_jobs` | R | readOnly, idempotent, openWorld |
| | `nexus_job_status` | R | readOnly, idempotent, openWorld |
| | `nexus_get_results` | R | readOnly, idempotent, openWorld |
| | `nexus_job_cost` | R | readOnly, idempotent, openWorld |
| **execute** *(opt-in)* | `nexus_estimate_cost` | R/$0 | readOnly*, openWorld — *see note |
| | `nexus_compile` | W | not-readOnly, not-destructive, not-idempotent, openWorld |
| | `nexus_submit` | W/$ | not-readOnly, not-destructive, **not-idempotent**, openWorld |
| | `nexus_submit_and_wait` | W/$ | not-readOnly, not-destructive, not-idempotent, openWorld |
| **manage** *(opt-in)* | `nexus_create_project` | W | not-readOnly, not-destructive, not-idempotent, openWorld |
| | `nexus_upload_circuit` | W | not-readOnly, not-destructive, not-idempotent, openWorld |
| | `nexus_upload_program` (QIR) | W | not-readOnly, not-destructive, not-idempotent, openWorld |
| **destructive** *(opt-in, double gate)* | `nexus_cancel_job` | X | not-readOnly, **destructive**, openWorld |
| | `nexus_delete_job` | X | not-readOnly, **destructive**, openWorld |
| | `nexus_archive_project` | X | not-readOnly, **destructive**, openWorld |
| | `nexus_delete_project` | X | not-readOnly, **destructive**, openWorld |

> **`nexus_estimate_cost` note:** `qnx.circuits.cost()` internally submits a real (free) `H2-1SC` syntax-checker
> job and blocks on it. It spends **0** credits but is **not** a pure read — it enqueues work on the shared
> resource — so by the read-only-strict rationale (§6) it lives in the **`execute`** toolset (opt-in), even
> though it is annotated `readOnly` for UX and its docstring documents the round-trip. For the pure read of an
> *existing* job's HQC cost use `nexus_job_cost` (`qnx.jobs.cost`), which stays in `read`.
> **`nexus_upload_program` is QIR-only.** The SDK also exposes a HUGR upload, but its own docstring
> warns *"HUGR support in Nexus is subject to change. Until full support is achieved any programs
> uploaded may not work in the future"* — we will not expose an endpoint the platform itself calls
> unstable. HUGR support can be added once the SDK removes that caveat.
> `openWorldHint: true` on every tool (all touch the cloud). There is no "costs money" annotation in the MCP vocabulary — spend-but-additive
> execution is `destructive: false` yet still gated for cost server-side (§6). All submit/execute tools are
> `idempotent: false` (each call is a new billed run); double-spend is prevented by the mandatory
> confirmation on billable submits, not by the hint.

## 5. Authentication

**We never handle the Nexus token.** The MCP spec (rev. 2025-11-25) confines the OAuth framework to
HTTP transports and says stdio servers SHOULD "retrieve credentials from the environment." We are stdio,
so we delegate 100% to `qnexus`, which owns a hardened device-code flow with refresh/rotation/revocation.

- **Status (read):** `nexus_auth_status` → `qnx.auth.is_logged_in()` (calls `GET /api/users/v1beta2/me`).
- **Login is out-of-band.** Users run `qnx login` (device-code) in their terminal **once**; `qnexus`
  caches tokens under `~/.qnx/auth/` (`token.json`, `id.json`). We do **not** expose an interactive login
  tool (the browser device flow does not fit an stdio tool call). `nexus_auth_status` returns actionable
  guidance ("run `qnx login`") when no valid session exists.
- **Nexus JupyterHub:** auth is automatic via `NEXUS_MANAGED_TOKENS`; the server must **not** call any
  login there. Detect and pass through.
- **Config/env:** `qnexus` reads pydantic-settings with prefix `NEXUS_` (`~/.qnexus/config`,
  `NEXUS_STORE_TOKENS`, `NEXUS_TOKEN_PATH`, `NEXUS_DOMAIN/HOST`). We surface only what we must and store
  nothing ourselves.
- **Hard rules:** never read, copy, print, log, or return the token or any cookie/secret; never accept a
  raw password as a tool argument.
- **Future remote variant:** must act as an OAuth 2.1 *resource server* — validate inbound `aud`, **never**
  pass the caller's token upstream (token-passthrough is spec-forbidden), and hold a *separate* upstream
  Nexus credential. Design the local server so this is an additive layer.

## 6. Permission model (the core)

Four layers, **all enforced server-side**. MCP tool annotations are UX hints only and are treated as
untrusted; the server is the source of truth.

**Layer 1 — Register-time omission.** A tool that is not permitted by the launch config
**does not appear in `tools/list` at all**. The agent cannot call what it cannot see. A single
`is_allowed(tool)` derived from config filters the exposed set. Annotation-only gating is insufficient.

**Layer 2 — Two-axis gating (a tool must pass ALL filters).**
- *Capability axis:* `--toolsets read,execute,manage,destructive` — **default: `read`** only.
- *Severity axis:* `--allow-spend` (default off), `--allow-hardware` (default off), `--allow-destructive`
  (default off).

**Layer 3 — Safe backend default.** The default execution backend is **`H2-1LE`** (noiseless emulator,
**0 HQC / free**). Any billable backend — real hardware (`H2-1`, `H1-1`) or noisy emulator (`*-1E`) —
requires `--allow-spend` **and** stays under the `--max-credits` per-call ceiling (passed to the SDK as
`max_cost`). Billable **emulators** additionally require a passing `quotas.check_quota("simulation")`
pre-check. Real **hardware** additionally requires `--allow-hardware`; note the qnexus SDK exposes **no
HQC-balance pre-check API** for hardware, so there the ceiling + mandatory confirmation are the only
pre-submission guards. Launch-flag gates run *before* cost estimation, so a forbidden device never even
enqueues the (free) estimation job. `valid_check=True` is passed on submit.

**Layer 4 — In-protocol confirmation (the differentiator).** Every `$` or `X` tool: estimate cost / name
the target resource → **`ctx.elicit()`** human confirmation *inside the protocol* → execute; refuse above
the `--max-credits` ceiling. A deterministic **idempotency tag** labels each submission; `start_execute_job` has no server-side
idempotency parameter, so the **mandatory confirmation on every billable submit is the real double-spend
protection** (a retry re-prompts). Shot counts are bounded to cap queue pressure.

**Default posture rationale (read-only strict).** Reads and executions are *not* comparable even when the
execution is free: execution enqueues work on a shared resource (queue/network saturation, blocking waits),
and — the subtle point — a future change, if mishandled, could turn a "free" lane into a billed one via
drift. Read-only-by-default removes that entire class of risk. Running circuits is a deliberate opt-in
(`--toolsets read,execute`), and even then defaults to the free `H2-1LE` lane.

**Config surface (launch flags / env):**

| Flag | Env | Default | Effect |
|---|---|---|---|
| `--toolsets` | `QNEXUS_MCP_TOOLSETS` | `read` | Which capability domains are exposed |
| `--allow-spend` | `QNEXUS_MCP_ALLOW_SPEND` | `false` | Permit billable (HQC) execution |
| `--allow-hardware` | `QNEXUS_MCP_ALLOW_HARDWARE` | `false` | Permit real-QPU targets (implies review) |
| `--allow-destructive` | `QNEXUS_MCP_ALLOW_DESTRUCTIVE` | `false` | Permit delete/cancel/archive |
| `--max-credits` | `QNEXUS_MCP_MAX_CREDITS` | `0` | Hard per-call HQC ceiling; 0 blocks all spend |
| `--projects` | `QNEXUS_MCP_PROJECTS` | *(all)* | Project allowlist, enforced on every mutating tool (reads are unaffected) |

## 7. Security controls (threat model → mitigation)

| Threat | Why it applies here | Mitigation |
|---|---|---|
| **Prompt injection → unwanted spend/mutation** | Injection enters via job names, uploaded files, *and Nexus-returned output* (CyberArk: outputs inject too) | Treat all args **and all Nexus output** as untrusted data; spend caps + confirmation gates enforced server-side, independent of the LLM |
| **Confused deputy / over-broad authority** | The agent could use our ambient `qnexus` credential beyond user intent | Least privilege; read-only default; per-op severity gates; optional per-project allowlist |
| **Tool poisoning / line-jumping / rug pull** | Tool descriptions enter LLM context at `tools/list` before any call (Invariant Labs PoC exfiltrated `~/.ssh/id_rsa`) | Clean, static, auditable descriptions; **no** hidden instructions; **no** silent `tools/list_changed` mutation; signed/hash-pinned releases; reserved package name |
| **Token theft / leakage** | Spec-named risk; every place code reads a token is a leak surface | Never handle the token; redact all secrets from logs, errors, tool results; short-lived + logout guidance |
| **Economic DoS (runaway spend)** | An injected loop could hammer `submit` | Server-side budget (`--max-credits` ceiling + bounded shot counts) + mandatory confirmation on billable submits + a sliding-window submission rate limit (covers the free lane) + serialized cloud mutations |
| **Path / config exfiltration** | If any tool touches the filesystem (e.g. reading a QASM file) | Schema-validate + canonicalize/allowlist paths; block traversal and reads of `~/.ssh`, dotfiles, MCP config, the token cache |

**Must-implement checklist:** server-enforced spend caps + confirmation on every `$`/`X` op · emulator +
read-only safe defaults · never handle/log/leak the token · rate limiting + idempotency keys + serialized
mutations · strict pydantic input validation + path confinement · clean static tool descriptions, no silent
tool-list mutation · masked errors + sanitized outputs.

## 8. Backend safety details (from verified `qnexus` v0.46.0 source)

- **Free lane (default):** device names ending in `LE` — e.g. `H2-1LE` — are noiseless, **free, zero HQC**.
- **Billable:** real hardware (`H2-1`, `H1-1`) and noisy emulators (`*-1E`) spend HQCs on `execute` /
  `start_execute_job` / `retry_submission`. `compile` consumes the *time-based compilation quota*, not HQCs.
- **Free syntax checker:** `H2-1SC`.
- **Native guardrail:** `execute(..., max_cost=<ceiling>, valid_check=True)` is a real SDK kwarg; check
  `qnx.quotas.check_quota("simulation")` before any billable submit. Quota names: `compilation`,
  `simulation`, `jupyterhub`, `database_usage`.
- **Helios note:** `HeliosConfig` lives at `qnx.models.HeliosConfig` (not top-level) and uses `system_name=`,
  not `device_name=`.

## 9. Error handling & output sanitization

- Auth errors → clear "run `qnx login`" guidance; never leak token/cookie material.
- Quota/cost errors → refuse with the reason, don't guess.
- Network/timeout → typed, actionable errors that never bait a blind retry loop; guidance never
  suggests retrying a `submit` (avoids double-spend). Waits are bounded (default 300 s, max 3600 s);
  on timeout the job keeps running and the error says how to poll it.
- All blocking SDK calls run in worker threads, so a slow or hung Nexus call can never freeze the
  server's event loop (the SDK's `jobs.wait_for` runs its own `asyncio.run`, which *requires* a
  loop-free thread).
- All `qnexus`/network exceptions mapped to short, redacted `ToolError` messages at the client
  boundary; anything unmapped is masked by `mask_error_details`. Known case: the Nexus jobs LIST
  endpoint can return 500s — that maps to an explicit "Nexus-side issue, do not retry in a loop"
  message rather than a hang or a cryptic failure.

## 10. Repo layout & packaging (adoptable-grade)

```
qnexus-mcp/
  LICENSE                      # Apache-2.0
  NOTICE                       # attribution + non-affiliation / nominative trademark use
  README.md                    # uvx install + copy-paste mcpServers config + disclaimer + `mcp-name:` marker
  SECURITY.md                  # private disclosure (qnexus has none — we exceed)
  CONTRIBUTING.md              # DCO sign-off (NOT a CLA)
  CODE_OF_CONDUCT.md           # Contributor Covenant
  CHANGELOG.md                 # Commitizen-generated
  pyproject.toml               # hatchling; [project.scripts] qnexus-mcp = "qnexus_mcp.cli:main"
  uv.lock                      # committed
  server.json                  # MCP Registry manifest
  .cz.toml                     # Commitizen / Conventional Commits / SemVer, tag_format v$version
  .pre-commit-config.yaml
  .github/
    workflows/{ci.yml,publish.yml}   # ci: ruff+mypy+pytest matrix 3.10–3.13 + pip-audit; publish: PyPI OIDC + registry
    ISSUE_TEMPLATE/…, PULL_REQUEST_TEMPLATE.md, dependabot.yml
  src/qnexus_mcp/
    __init__.py
    cli.py                     # console entry point
    config.py                  # toolsets + severity gates + ceilings + allowlist (pydantic)
    backends.py                # device classification (free / billable / hardware)
    sanitize.py                # secret redaction (keys and values)
    permissions.py             # ToolSpec registry + register-time omission (Layer 1)
    client.py                  # NexusClient Protocol + qnexus wrapper; error translation
    context.py                 # per-server state binding + thread offload for blocking SDK calls
    guards.py                  # SpendGuard, project allowlist, rate limit, idempotency
    server.py                  # FastMCP app; registers only permitted tools
    tools/{read,execute,manage,destructive}.py
    py.typed
  tests/                       # qnexus mocked; asserts guardrail logic + tool-schema snapshot
    smoke/                     # opt-in live, read-only + one free H2-1LE run
```

- **License:** Apache-2.0 (every Quantinuum/CQCL repo is Apache-2.0; identical license removes the
  mechanical adoption gate; §3 patent grant matters in patent-dense quantum). `NOTICE` carries the
  non-affiliation + nominative-use statement.
- **Toolchain mirrors `qnexus`:** hatchling, ruff, mypy + `pydantic.mypy`, pytest, `py.typed`,
  Commitizen/Conventional Commits/SemVer, committed `uv.lock`. We **exceed** its governance: `qnexus` ships
  no `SECURITY.md`/`CONTRIBUTING.md`/`CODE_OF_CONDUCT.md`; we do (+ DCO for clean IP provenance).

## 11. Distribution & publishing

1. **PyPI** as `qnexus-mcp`, via **Trusted Publishing (OIDC in GitHub Actions)** — no static token. Runs
   via `uvx qnexus-mcp`.
2. **PyPI ownership proof for the registry:** `<!-- mcp-name: io.github.<owner>/qnexus-mcp -->` in the README.
3. **MCP Registry:** `mcp-publisher` → `server.json` (`name = io.github.<owner>/qnexus-mcp` matching the
   marker; `registryType: pypi`; `identifier: qnexus-mcp`; `transport.type: stdio`; `runtimeHint: uvx`;
   `environmentVariables` for the toolset/gate flags). `mcp-publisher login github` (device-code) grants
   the `io.github.*` namespace. Automate re-publish on release.
4. **Namespace = honesty signal.** `io.github.<owner>/*` = community. `com.quantinuum.*` requires DNS/TXT
   proof of `quantinuum.com` — only Quantinuum can claim it, which *is* the adoption handoff.
5. **Client configs:** ship copy-paste `.mcp.json` / Claude Code / Cursor / VS Code snippets.

## 12. Testing strategy

- **Unit (qnexus mocked):** tool schemas; arg validation; **guardrail logic** — e.g. `submit` refuses without
  `elicit` confirmation; refuses a billable backend without `--allow-spend`; refuses above `max_cost`;
  destructive tools absent from `tools/list` without `--allow-destructive`.
- **Snapshot test** of the full tool catalog (names, descriptions, annotations, input schemas) so the
  agent-facing surface can't drift silently.
- **Opt-in live smoke** (env-gated): read-only calls + one tiny free `H2-1LE` run. **Billable submits never
  run in CI.**
- Optional **agent-run eval harness** once tools stabilize.

## 13. Verify against live SDK before wiring (flagged discrepancies)

**Resolution (2026-07-21):** every item below was confirmed against the installed SDK and/or live Nexus
during M1–M3 (the free-emulator string is `H2-1LE`; `circuits.cost` does submit a blocking free
syntax-check job; destructive project lookups use the SDK's exact-match `projects.get(name=...)`).
Kept for the record:

1. Docs API index is **stale vs code**: `login_no_interaction` is `qnx.auth.login_no_interaction` (not
   top-level); `login_with_token` *is* top-level. (We use neither for login, but confirm `is_logged_in`.)
2. Canonical device strings are `H2-1E` / `H2-1LE` / `H2-1SC` / `H2-1` (+ H1 analogues); a doc summary's
   `"H2-Emulator"` is unverified — **confirm the exact free-emulator string live** before defaulting to it.
3. Confirm exact signatures/kwargs of `CircuitRef.download_circuit()`,
   `CompilationResultRef.get_output()`, `ExecutionResultRef.download_result()` before wiring results.
4. Confirm `qnx.circuits.cost()` behavior (blocking free `H2-1SC` job) on the event's actual account.
5. Confirm the token-cache path (`~/.qnx/auth/`) — **the design deliberately never depends on it**, but the
   `nexus_auth_status` guidance message should be accurate.

## 14. Path to official (honest)

No documented case exists of a *community-built* MCP server being taken over and rebranded as a vendor's
official one — the known official servers were first-party from day one. So the
realistic route is: **build to first-party quality → gain traction + registry listings (+ real use during
the Quantathon) → propose Quantinuum adopt/co-maintain.** Adoption is earned. The design keeps the handoff
to a single mechanical step (re-namespacing `io.github.*` → `com.quantinuum.*`). Signals that maximize the
odds: identical Apache-2.0 license, DCO (not CLA) IP cleanliness, dependence only on the *published* PyPI
`qnexus`, `SECURITY.md` + OIDC publishing + Dependabot, green typed CI, SemVer, >1 maintainer, and traction.

## 15. Milestones

**Status (2026-07-21): M0–M4 DONE and committed; read + execute paths verified live against real Nexus
(Bell state on `H2-1LE`). M5 (public flip + first release) pending — it needs the maintainer's explicit
go-ahead.**

- **M0 — Repo hygiene (public-ready first commit):** LICENSE, NOTICE, README + disclaimer, SECURITY,
  CONTRIBUTING (DCO), CoC, CI skeleton, `pyproject`. No secrets. *(Gate before the repo is made public.)*
- **M1 — Read toolset + auth status + permission scaffolding** (register-time omission, config surface).
- **M2 — `execute` toolset** (compile, submit to free `H2-1LE`, submit_and_wait) with in-protocol
  confirmation, `max_cost`, quota pre-check, idempotency.
- **M3 — `manage` + `destructive` toolsets** behind their gates.
- **M4 — Packaging & publishing** (PyPI OIDC, `server.json`, registry, client-config snippets).
- **M5 — Public flip + Quantathon rollout** (announce, invite participants to install).

## 16. Sources

Research (2026-07-20), conducted against primary sources. Full write-ups live in
[`research/`](research/):
- MCP security & authorization (spec rev. 2025-11-25; OAuth 2.1 / PKCE / RFC 8707 / RFC 9728; tool-poisoning, confused-deputy, token-passthrough, rug-pull threat classes; tool annotations).
- `qnexus` v0.46.0 API surface (verified against source at `github.com/Quantinuum/qnexus`).

Primary references: <https://modelcontextprotocol.io> · <https://docs.quantinuum.com/nexus/> ·
<https://github.com/Quantinuum/qnexus> · <https://github.com/jlowin/fastmcp>
