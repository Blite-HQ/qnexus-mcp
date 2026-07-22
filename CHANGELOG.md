# Changelog

All notable changes are documented here. This project follows [Semantic Versioning](https://semver.org)
and [Conventional Commits](https://www.conventionalcommits.org).

## [Unreleased]

## [0.1.0] - 2026-07-21

### Added

- **Read toolset** (always on): `nexus_auth_status`, `nexus_whoami`, `nexus_list_devices`,
  `nexus_device_status`, `nexus_list_projects`, `nexus_get_quota`, `nexus_list_jobs`,
  `nexus_job_status`, `nexus_job_cost`, `nexus_get_results`.
- **Execute toolset** (`--toolsets execute`): `nexus_compile`, `nexus_estimate_cost`, `nexus_submit`,
  `nexus_submit_and_wait`. Defaults to the free `H2-1LE` emulator; billable devices are gated by
  `--allow-spend` / `--allow-hardware` / `--max-credits`, a `simulation`-quota pre-check (emulators),
  plus an in-protocol confirmation.
- **Manage toolset** (`--toolsets manage`): `nexus_create_project`, `nexus_upload_circuit`,
  `nexus_upload_program` (QIR).
- **Destructive toolset** (`--toolsets destructive` + `--allow-destructive`): `nexus_cancel_job`,
  `nexus_delete_job`, `nexus_archive_project`, `nexus_delete_project`, each behind an in-protocol
  confirmation that names the exact target.
- Server-side permission gating with **register-time omission**; read-only by default.
- `--projects` / `QNEXUS_MCP_PROJECTS` project allowlist, enforced on every mutating tool.
- Submission rate limiting (sliding window) and serialized cloud mutations.
- Secret redaction (keys and values) and masked tool errors; SDK/network failures are translated into
  short, actionable, redacted messages (auth → "run `qnx login`", Nexus 5xx → "Nexus-side issue, do
  not retry in a loop").
- Server-level `instructions`, surfaced to the connecting agent at the MCP handshake: check auth
  first, how to tell an agent-fixable guard error from one that needs the human, the known-flaky
  `nexus_list_jobs` endpoint, and a suggested end-to-end flow for running a circuit.
- Snapshot test freezing the full agent-facing tool catalog.

### Fixed

- `nexus_list_devices` now returns plain, JSON-safe fields instead of a raw pytket object the MCP
  structured-output layer couldn't serialize.
- Malformed OpenQASM input now names the exact syntax problem instead of a generic failure.
- Looking up a job by an unknown id now gives the same actionable "no match, list to find the right
  one" message as an unknown project, instead of an opaque error.
- `SpendGuard` reports every missing launch flag at once (e.g. `--allow-spend` and `--allow-hardware`
  together), so one server restart covers it instead of discovering the second requirement only after
  fixing the first.

### Security

- Authentication is delegated entirely to `qnexus`; the server never reads, stores, logs, or returns the
  Nexus token.
- Destructive project operations resolve their target by **exact** name via the SDK's unique-match
  lookup; an ambiguous or missing name aborts instead of acting.
- Blocking SDK calls run in worker threads with bounded waits (default 300 s), so a slow or hung Nexus
  call can never freeze the server or hang the session.
- CI/publish workflows run with least-privilege tokens and actions pinned to commit SHAs; CI runners are
  further hardened with `step-security/harden-runner`, and a coverage floor guards against a large
  untested regression; releases publish to PyPI exclusively via Trusted Publishing (OIDC, no stored
  tokens); Dependabot + `osv-scanner` watch the dependency tree; `main` is protected by a repository
  ruleset (required CI checks, no force-push, no deletion).

### Verified

- Read and execute paths verified against live Nexus (2026-07-21): a Bell circuit compiled and ran on the
  free `H2-1LE` emulator with correct results.
- The full read toolset verified against a real MCP client (not mocks) over the actual stdio protocol,
  including a fresh, independent agent exercising the auth, error-handling, and guard-rail behavior
  described in the server's `instructions`.
