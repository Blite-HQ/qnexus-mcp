# Research — how we designed `qnexus-mcp`

This folder documents the research behind [`../DESIGN.md`](../DESIGN.md). Before writing a line of the
server, we studied how reputable, real-world MCP servers are built, secured, governed, and distributed —
so `qnexus-mcp` starts at the quality bar of the best incumbents (and, where we found a gap, above it).

All research was conducted on **2026-07-20** against primary sources (spec pages, actual repositories and
their source files, official docs, and package registries). Claims that could not be verified from a
primary source are flagged in-place. Everything here is a snapshot in time — the MCP ecosystem moves fast
(the spec had a new revision on 2025-11-25; the registry API froze at v0.1 on 2025-10-24; MCP joined the
Linux Foundation on 2025-12-09) — re-verify dated claims before relying on them.

## What's here

| Doc | Answers |
|---|---|
| [`01-mcp-ecosystem-audit.md`](01-mcp-ecosystem-audit.md) | How leading MCP servers are built. Per-project profiles (is it open source? language, community, how it was developed, the challenges they hit and how they solved them, their gating/security strategy, the tooling and practices in their repos). Comparative matrix, patterns to adopt, anti-patterns, and the reference blueprint we chose. |
| [`02-security-and-authorization.md`](02-security-and-authorization.md) | The MCP security model (local stdio vs remote HTTP auth), the known attack classes against MCP servers, how projects protect themselves, the threat model for a credit-spending quantum-cloud server, the controls we must build, and the tool-annotation scheme. |
| [`03-oss-and-adoptability.md`](03-oss-and-adoptability.md) | What makes an open-source repo credible and vendor-adoptable: license, governance, community norms, the tooling/methodologies real projects use, packaging, the official MCP Registry, and the honest "path to official." |
| [`04-qnexus-sdk-surface.md`](04-qnexus-sdk-surface.md) | The real, verified API surface of the `qnexus` SDK we wrap — auth flow, resources, the capability→tool map with credit/destructive classification, backend safety, and the items to re-verify before wiring. |

## Method

Four independent research streams ran in parallel, each tied to a design decision:

1. **Ecosystem audit** — read the READMEs and source files of ~13 MCP servers/frameworks via `gh api` +
   raw source, plus the MCP spec and Anthropic's tool-design guidance.
2. **Security & authorization** — the MCP spec's authorization and security-best-practices pages, the
   relevant IETF RFCs, and the public MCP-security literature (tool poisoning, line jumping, confused
   deputy, token passthrough).
3. **OSS adoptability & distribution** — Quantinuum's own repos (via `gh api`), the MCP Registry docs,
   PyPI packaging, and the OSS-trust literature.
4. **`qnexus` SDK surface** — the actual `qnexus` v0.46.0 source at tag `v0.46.0`, cross-checked against
   docs.quantinuum.com.

Each stream's full source list is at the bottom of its document.

## One-line takeaways

- **Build on FastMCP 2.0 (Python).** We wrap a Python SDK; FastMCP gives us annotations, tag-based
  enable/disable, `ctx.elicit()` confirmation, structured output, and multi-transport for free.
- **Model gating on GitHub's `github-mcp-server`** (annotations are the source of truth; the *server*
  enforces read-only by filtering the tool list — register-time omission).
- **Enforce everything server-side.** MCP tool annotations are UX hints, explicitly *not* security.
- **Ship the thing nobody else ships:** an in-protocol cost-preview + confirmation gate before any credit
  spend or destructive action. None of Stripe/PayPal/Grafana/GitLab/Atlassian/Notion do this in-protocol.
- **Match Quantinuum's toolchain and license (Apache-2.0)** so the repo reads as first-party and adoption
  is a single mechanical step.
