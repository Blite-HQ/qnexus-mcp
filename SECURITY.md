# Security Policy

`qnexus-mcp` mediates access to a paid quantum-computing cloud. We take security seriously.

## Reporting a vulnerability

**Do not open a public issue for security reports.** Instead, use GitHub's private
[**Report a vulnerability**](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
flow on this repository (Security → Advisories → Report a vulnerability).

We aim to acknowledge reports within 3 business days and to provide a remediation timeline within 10.

## Supported versions

| Version | Supported |
|---|---|
| `0.x` (latest) | ✅ |
| older `0.x` | ❌ |

## Scope & design guarantees

- The server **never reads, stores, logs, or returns** your Nexus authentication token; authentication is
  delegated entirely to the `qnexus` SDK.
- Credit-spending and destructive actions are **off by default**, require explicit launch flags, and are
  gated by an in-protocol confirmation plus a server-side cost ceiling.
- Tool descriptions are static and auditable; the server does not mutate its tool list at runtime.

See [`docs/DESIGN.md`](docs/DESIGN.md) §7 and [`docs/research/02-security-and-authorization.md`](docs/research/02-security-and-authorization.md)
for the full threat model.
