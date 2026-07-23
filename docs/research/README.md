# Research: the evidence behind `qnexus-mcp`

This folder documents the primary-source research behind [`../DESIGN.md`](../DESIGN.md).

All research was conducted on **2026-07-20** against primary sources (spec pages, official docs, actual
source repositories, and package registries). Claims that could not be verified from a primary source are
flagged in-place. Everything here is a snapshot in time; the MCP ecosystem moves fast (the spec had a
new revision on 2025-11-25; the registry API froze at v0.1 on 2025-10-24; MCP joined the Linux Foundation
on 2025-12-09); re-verify dated claims before relying on them.

## What's here

| Doc | Answers |
|---|---|
| [`02-security-and-authorization.md`](02-security-and-authorization.md) | The MCP security model (local stdio vs remote HTTP auth), the known attack classes against MCP servers, the threat model for a credit-spending quantum-cloud server, the controls the server must implement, and the tool-annotation scheme. |
| [`04-qnexus-sdk-surface.md`](04-qnexus-sdk-surface.md) | The real, verified API surface of the `qnexus` SDK we wrap: auth flow, resources, the capability→tool map with credit/destructive classification, backend safety, and the items re-verified before wiring. |
| [`05-user-onboarding-friction.md`](05-user-onboarding-friction.md) | Every problem a real first user hit connecting agents to v0.1.0 (Windows Claude Desktop / VS Code / WSL Claude Code, 2026-07-22): server bugs, per-platform connection traps, and ecosystem behavior — each with verified root cause and status. The evidence base for `../TROUBLESHOOTING.md` and the README setup guide. |

Each document's full source list is at its end.
