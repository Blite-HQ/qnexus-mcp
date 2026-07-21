# Changelog

All notable changes are documented here. This project follows [Semantic Versioning](https://semver.org)
and [Conventional Commits](https://www.conventionalcommits.org).

## [Unreleased]

### Added

- **Read toolset** (always on): `nexus_auth_status`, `nexus_whoami`, `nexus_list_devices`,
  `nexus_list_projects`, `nexus_get_quota`, `nexus_list_jobs`, `nexus_job_status`, `nexus_job_cost`,
  `nexus_get_results`.
- **Execute toolset** (`--toolsets execute`): `nexus_compile`, `nexus_estimate_cost`, `nexus_submit`,
  `nexus_submit_and_wait`. Defaults to the free `H2-1LE` emulator; billable devices are gated by
  `--allow-spend` / `--allow-hardware` / `--max-credits` plus an in-protocol confirmation.
- **Manage toolset** (`--toolsets manage`): `nexus_create_project`, `nexus_upload_circuit`.
- **Destructive toolset** (`--toolsets destructive` + `--allow-destructive`): `nexus_cancel_job`,
  `nexus_delete_job`, `nexus_archive_project`, `nexus_delete_project` — each behind an in-protocol
  confirmation that names the exact target.
- Server-side permission gating with **register-time omission**; read-only by default.
- Secret redaction (keys and values) and masked tool errors.

### Security

- Authentication is delegated entirely to `qnexus`; the server never reads, stores, logs, or returns the
  Nexus token.

### Verified

- Read and execute paths verified against live Nexus (2026-07-21): a Bell circuit compiled and ran on the
  free `H2-1LE` emulator with correct results.
