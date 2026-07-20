# 02 — Security & authorization: how MCP servers protect themselves

**Researched 2026-07-20.** Sources: the MCP authorization & security-best-practices spec pages (revisions
2025-06-18 and 2025-11-25), the relevant IETF RFCs, and the public MCP-security literature. Full source
list at the end.

This is the document the whole `qnexus-mcp` security posture derives from. The server **spends real quantum
credits** and can **create/upload/delete cloud resources**, so it is a higher-stakes target than a typical
read-only MCP server.

---

## The authorization model: local (stdio) vs remote (HTTP)

The MCP authorization framework is explicitly **transport-level and HTTP-only**. From the spec's protocol
requirements (both revisions):

- Authorization is **OPTIONAL**.
- HTTP transports **SHOULD** conform to the OAuth framework.
- **"Implementations using an STDIO transport SHOULD NOT follow this specification, and instead retrieve
  credentials from the environment."**

So the entire OAuth apparatus is for **remote** servers. A **local stdio server inherits the trust boundary
of the process that launched it** and reads credentials from the environment / local config.

**`qnexus-mcp` is a local stdio server → we are on the "retrieve credentials from the environment" path.**
Authentication is done out-of-band by `qnexus` itself (`qnx login` device flow caches a token on disk); our
server just builds a client that reads that token. **We do not run OAuth, mint/receive bearer tokens, or
implement RFC 8707/9728/8414.** (If we ever ship a remote variant, the full framework below becomes mandatory.)

### The remote (HTTP) obligations, for reference / a future hosted variant

The latest revision at research time is **2025-11-25** (supersedes 2025-06-18): it adds OAuth **Client ID
Metadata Documents** (preferred over Dynamic Client Registration, now demoted to MAY), mandatory **PKCE
`S256`** with a metadata capability check (client MUST refuse if `code_challenge_methods_supported` is
absent), OIDC Discovery as an RFC 8414 alternative, and a formal **step-up / incremental-scope** flow.

Roles: the **MCP server is an OAuth 2.1 Resource Server**; the **client is the OAuth client**; a separate
**Authorization Server** issues tokens. Key MUSTs: PKCE; **RFC 8707 Resource Indicators** (`resource=` on
both authorization and token requests); **RFC 9728 Protected Resource Metadata**; **RFC 8414** AS metadata
(or OIDC); **audience validation** (the server MUST verify tokens were issued for *it*, RFC 9068 `aud`);
HTTPS everywhere; short-lived tokens with refresh rotation; least-privilege `scopes_supported`.

**Should we ever handle tokens ourselves? No — not for the local server.** (1) the spec says stdio servers
SHOULD NOT; (2) `qnexus` already owns a hardened flow (we inherit refresh/rotation/revocation); (3) every
place code touches a token is a leak surface — the safest token is one our code never reads; (4) as a
widely-installed binary next to a live spend credential, we minimize what we hold. The **only** exception is
a future remote variant, which must validate inbound `aud`, **never** pass the caller's token upstream, and
hold a **separate** upstream Nexus credential.

---

## How MCP servers get attacked (the threat classes)

These are the documented attack classes against MCP servers, drawn from the spec's security-best-practices
page and the public literature (Invariant Labs, Trail of Bits, CyberArk, Simon Willison):

- **Prompt injection → tool poisoning.** Malicious instructions hidden in a tool's `description`/`inputSchema`
  enter the LLM's context at `tools/list` **before any tool is called** ("line jumping", Trail of Bits). An
  Invariant Labs PoC used a poisoned description to exfiltrate `~/.ssh/id_rsa`. Injection also arrives via
  tool **inputs** (a job name, an uploaded file) and — per CyberArk's "poison everywhere" — via tool
  **outputs** the model then acts on.
- **Confused deputy.** The server holds the user's full authority; a lower-trust LLM drives it into actions
  the user never intended. OAuth proxies with static client IDs + DCR + consent cookies can also leak auth codes.
- **Token passthrough.** Forwarding a client-supplied token straight to the downstream API — **explicitly
  forbidden** by the spec ("MUST NOT accept any tokens that were not explicitly issued for the MCP server");
  it breaks rate-limits, audit trails, and trust boundaries.
- **Rug pull.** A tool's description mutates *after* the user approved it (via `notifications/tools/list_changed`).
- **Token theft.** The cached credential ends up in logs, errors, tool results, or an LLM transcript
  (transcripts are frequently shipped to third parties).
- **Economic DoS.** For a spending server, an agent retry-storm or injected loop is direct financial loss +
  quota exhaustion.
- **Input abuse / path traversal.** Malformed payloads or a "read this file" path that escapes the workspace
  and exfiltrates secrets.
- **Local server compromise / malicious startup.** A one-click launch command runs with the user's
  privileges; DNS-rebinding can reach a locally-listening server.
- **Remote-only:** session hijacking (guessable/persistent session IDs), SSRF via OAuth-discovery URLs
  (`169.254.169.254` metadata theft), supply-chain compromise of dependencies or a typosquatted package.

## Threat model for `qnexus-mcp`

| Threat | Why it applies here | Mitigation we build |
|---|---|---|
| Prompt injection → unwanted spend/mutation | Tools submit paid jobs and can delete projects; injection can arrive via inputs *or* Nexus-returned output | Treat all args + all Nexus output as untrusted data; **server-side** caps + confirmation independent of the LLM; prefer structured output |
| Confused deputy / over-broad authority | The server holds the user's Nexus authority; the LLM is lower-trust | Least privilege; **emulator + read-only defaults**; per-op gates; optional project allowlist |
| Tool poisoning / line jumping / rug pull | As a published, adoptable server we're a supply-chain target | Clean, static, auditable descriptions; **no** hidden instructions; **no** silent tool-list mutation; signed/pinned releases; guard the token file |
| Token theft / leakage | The cached token = full spend authority | Never handle/log/return the token; redact secrets everywhere; short-lived + logout guidance |
| Economic DoS (runaway spend) | Every mutate can cost money / finite quota | Server-side budget (`--max-credits`, max shots/jobs/concurrency); rate limiting; **idempotency keys**; serialized mutations |
| Destructive resource ops | `qnexus` can delete projects/jobs irreversibly | `destructiveHint:true`; explicit confirmation naming the target; **off unless `--allow-destructive`** |
| Input abuse / path traversal | We accept paths + payloads and hand them to the SDK/filesystem | Strict schema validation; canonicalize + allowlist paths; block `~/.ssh`, dotfiles, MCP config, the token cache |
| Local compromise / malicious startup | We sit next to a live spend credential | Trusted package + pinned versions + integrity hashes; **stdio only** (no listening socket); document the exact launch command; least OS privilege |
| *(remote only)* token passthrough, session hijack, SSRF, supply chain | Only if we host an HTTP variant | Validate `aud`; separate upstream credential; CSPRNG session IDs bound to user, never used for auth; block private IP ranges; pin+hash deps, SBOM, signed artifacts |

## Must-implement controls (checklist)

- **Auth:** delegate to `qnexus`; never read/copy/print/log/return the token; redact credentials from all
  logs/errors/results; fail closed with "run `qnx login`" (never accept a raw password via a tool arg).
- **Safe defaults:** emulator not hardware; read-only by default; no omnibus destructive tools.
- **Confirmation:** every spend/destructive op requires an explicit gate naming target + cost estimate +
  backend, and emits honest annotations so the client's own confirmation UI also fires.
- **Spend/rate limiting (server-enforced, independent of the LLM):** hard caps (shots/job, jobs/session,
  concurrency, cumulative credit ceiling); **idempotency keys**; rate-limit + serialize mutations.
- **Input validation & isolation:** pydantic/JSON-Schema on every arg; path canonicalization + workspace
  confinement; size/shape limits.
- **Tool-surface integrity:** static, human-auditable descriptions; no `tools/list_changed` mutation after
  connect; publish the expected tool list so clients can pin it.
- **Supply chain:** pinned + hash-locked deps; minimal surface; SBOM; Dependabot/`pip-audit`; signed,
  reproducible releases; reserved package name.
- **Auditability:** structured audit log of every call (tool, sanitized args, backend, estimated cost,
  decision, status) with secrets redacted; local only.

## Tool annotations — a permission *signal*, not a control

All four annotations are **hints**; the spec: *"clients MUST treat them as untrusted unless from a trusted
server."* We set them honestly so trusted-server clients (Claude Code, etc.) render the right consent and
parallelism UX (Claude Code runs `readOnlyHint:true` tools concurrently; `destructiveHint:true` triggers a
confirmation dialog) — but the real control is always server-side.

| Meaning | Default |
|---|---|
| `readOnlyHint` — does not modify its environment | `false` |
| `destructiveHint` — modification may be destructive (only meaningful when not read-only) | `true` |
| `idempotentHint` — repeat call has no additional effect | `false` |
| `openWorldHint` — interacts with an open world of external entities | `true` |

Because the defaults are conservative, **omitting** annotations makes every tool look destructive/external —
so annotate deliberately. Every `qnexus-mcp` tool talks to the cloud → **`openWorldHint: true` everywhere.**
There is **no "costs money" annotation** — mark spend-but-additive execution `destructiveHint:false` yet
still gate it server-side for cost; set `idempotentHint:false` on all submit/execute tools (each call is a
new billed run) and make *retries* safe with idempotency keys instead of lying about idempotency.

---

## Caveats / verification flags
- The Security Best Practices page is living content; some sections post-date the 2025-06-18 freeze —
  re-check the dated URL before shipping.
- Annotations are advisory only — any claim that an annotation *enforces* anything is wrong.
- The exact `qnexus` token-cache path/env var could not be pinned from primary docs in this pass; the design
  **deliberately never depends on it**.

## Sources (observed 2026-07-20)
- MCP Authorization spec: modelcontextprotocol.io `/specification/2025-06-18/basic/authorization`,
  `/specification/2025-11-25/basic/authorization`.
- MCP Security Best Practices: `/specification/2025-06-18/basic/security_best_practices` (+ 2025-11-25).
- MCP Tools spec: `/specification/2025-06-18/server/tools`. Tool-annotation blog: blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/.
- Invariant Labs, "Tool Poisoning Attacks" (2025-04-01); Simon Willison, "MCP has prompt injection security
  problems" (2025-04-09); CyberArk "poison everywhere" (2025).
- IETF: OAuth 2.1 draft-13; RFC 8707, 9728, 8414, 7591, 9700, 6750, 9068.
- qnexus auth docs: docs.quantinuum.com/nexus/nexus_api/auth.html.
