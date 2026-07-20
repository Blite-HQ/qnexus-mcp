# 04 — The `qnexus` SDK surface we wrap

**Researched 2026-07-20** against **`qnexus` v0.46.0** (tag `v0.46.0`, commit `30244a2e…`, released
2026-06-30), read directly from source and cross-checked with docs.quantinuum.com. The repo moved from
`CQCL/qnexus` to **`github.com/Quantinuum/qnexus`** (Apache-2.0). Items that could not be verified from
source are flagged; **we did not invent any function name.**

---

## Authentication (verified against `qnexus/client/auth.py`, `utils.py`, `config.py`)

| Function | Top-level? | Notes |
|---|---|---|
| `qnx.login(force=False, region=None)` | yes | Browser **device-code** OAuth flow |
| `qnx.login_with_credentials(...)` | yes | Interactive email/password + MFA |
| `qnx.auth.login_no_interaction(user, pwd, ...)` | **no** (`qnx.auth.`) | Non-interactive user/pwd |
| `qnx.login_with_token(refresh_token)` | yes | In-memory only; writes nothing to disk |
| `qnx.logout()` | yes | Deletes token files + reloads client |
| `qnx.auth.is_logged_in() -> bool` | via `qnx.auth` | Checks disk tokens + `GET /api/users/v1beta2/me` — **the "check auth status" primitive** |

- **Device-code flow:** `POST /auth/device/device_authorization` (`client_id="scales"`, `scope="myqos"`) →
  opens `verification_uri_complete` → polls `POST /auth/device/token` until 200.
- **Token cache:** `~/.qnx/auth/` — `token.json` (refresh, cookie `myqos_oat`) + `id.json` (access, cookie
  `myqos_id`); gated by `CONFIG.store_tokens` (default `True`).
- **Config/env:** pydantic-settings, prefix **`NEXUS_`**, file `~/.qnexus/config` (override
  `NEXUS_CONFIG_FILE`); keys include `NEXUS_DOMAIN`/`NEXUS_HOST`, `NEXUS_STORE_TOKENS`, `NEXUS_TOKEN_PATH`.
- **Nexus JupyterHub:** env `NEXUS_MANAGED_TOKENS` → managed mode; the refresh token is server-managed. **Do
  not call `qnx.login()` inside the Hub** — auth is automatic.

**Our stance:** the MCP server only calls `qnx.auth.is_logged_in()` and builds a client from the cached
token. Login is out-of-band (`qnx login` in the terminal, once). We never read/store the token.

## Backends & the free lane (verified from docstrings + systems docs)

- Config classes at top level (`qnx.*`): `QuantinuumConfig`, `SeleneConfig`, `SelenePlusConfig`, `AerConfig`,
  `BraketConfig`, `IBMQConfig`, `QulacsConfig`, `BackendConfig`. **`HeliosConfig` is `qnx.models.HeliosConfig`**
  (not top-level) and uses `system_name=` not `device_name=`.
- **H2 device strings:** `H2-1` = real hardware; `H2-1E` = **noisy** emulator (**consumes HQCs**);
  **`H2-1LE` = noiseless emulator (FREE, no HQCs)**; `H2-1SC` = free syntax checker. Same pattern for H1.
  → **The safe default backend is `H2-1LE`.** (The string `"H2-Emulator"` seen in one doc summary is
  **unverified** — treat `H2-1E`/`H2-1LE`/`H2-1SC` as canonical; **confirm the exact string live** before
  defaulting to it.)

## Capability → MCP tool map

Class: **R** = read/safe · **W** = write/create · **$** = credit-spending (HQCs) · **X** = destructive.

| SDK operation | Function (verified?) | Class | Proposed tool | Guardrail |
|---|---|---|---|---|
| Auth status | `qnx.auth.is_logged_in()` ✅ | R | `nexus_auth_status` | — |
| List/get projects | `qnx.projects.get_all/get` ✅ | R | `nexus_list_projects` | — |
| Create project | `qnx.projects.create/get_or_create` ✅ | W | `nexus_create_project` | — |
| Update/archive project | `qnx.projects.update(archive=)` ✅ | W/X | `nexus_archive_project` | confirm on archive |
| Delete project | `qnx.projects.delete()` ✅ | **X** | `nexus_delete_project` | archived-first + explicit confirm; deletes all data |
| List devices | `qnx.devices.get_all()` ✅ | R | `nexus_list_devices` | — |
| Device status | `qnx.devices.status(QuantinuumConfig)` ✅ | R | `nexus_device_status` | QuantinuumConfig only; N/A for emulators |
| Backend capabilities | `qnx.devices.supports_*` ✅ | R | `nexus_backend_supports` | — |
| Upload circuit | `qnx.circuits.upload(Circuit)` ✅ | W | `nexus_upload_circuit` | validate pytket; needs a project |
| Get/download circuit | `qnx.circuits.get_all/get` ✅ + `CircuitRef.download_circuit()` | R | `nexus_get_circuit` | — |
| Estimate cost | `qnx.circuits.cost()` ✅ | $0 | `nexus_estimate_cost` | ⚠ submits a real free `H2-*SC` job and blocks — belongs in the opt-in `execute` toolset |
| Upload HUGR/QIR/WASM/GPU | `qnx.hugr/qir/wasm_modules/gpu_decoder_configs.*` ✅ | W | `nexus_upload_program` | HUGR experimental |
| Submit compile | `qnx.start_compile_job()` / `qnx.compile()` ✅ | W | `nexus_compile` | consumes time-based **compilation** quota, not HQCs |
| **Submit execute** | `qnx.start_execute_job()` / `qnx.execute()` ✅ | **$** | `nexus_submit` | **default `*-1LE` (free); refuse hardware/`*-1E` unless allowed + `max_cost` set**; keep `valid_check=True` |
| Job status / list | `qnx.jobs.status/get_all` ✅ | R | `nexus_job_status` | — |
| Wait for job | `qnx.jobs.wait_for()` ✅ | R (blocking) | (internal to `submit_and_wait`) | set timeout; prefer poll loop |
| Job HQC cost | `qnx.jobs.cost/cost_confidence()` ✅ | R | `nexus_job_cost` | — |
| Fetch results | `qnx.jobs.results()[i].download_result()` / `qnx.results.get(id)` ✅ | R | `nexus_get_results` | — |
| Retry job | `qnx.jobs.retry_submission()` ✅ | **$** | `nexus_retry_job` | re-spends HQCs; confirm |
| Cancel job | `qnx.jobs.cancel()` ✅ | X | `nexus_cancel_job` | mutates remote; confirm |
| Delete job | `qnx.jobs.delete()` ✅ | **X** | `nexus_delete_job` | confirm |
| Quotas | `qnx.quotas.get_all/get/check_quota` ✅ | R | `nexus_get_quota` | names: `compilation`, `simulation`, `jupyterhub`, `database_usage` |
| Credentials list | `qnx.credentials.get_all()` ✅ | R | *(out of scope)* | never expose secret values |

## Guardrail targets (the money & danger)

- **Spends HQCs ($):** `execute`/`start_execute_job` and `retry_submission` — but **only** on hardware
  (`H2-1`, `H1-1`) or **noisy** emulators (`*-1E`). `compile` uses the time-based **compilation** quota, not HQCs.
- **The native ceiling exists:** `execute(..., max_cost=<HQC ceiling>, valid_check=True)` are real SDK
  kwargs; gate on `qnx.quotas.check_quota("simulation")` before any billable submit. We expose `max_cost`
  as a mandatory MCP guardrail.
- **Destructive (X):** `projects.delete` (all data; archived-first), `jobs.delete`, `jobs.cancel`,
  `projects.update(archive=True)`, metadata overwrites, any credential delete.

## Minimal submit-and-poll idiom (verified against docstrings + getting_started.html)

```python
import qnexus as qnx
from pytket.circuit import Circuit

if not qnx.auth.is_logged_in():
    qnx.login()                                   # out-of-band, once

project  = qnx.projects.get_or_create(name="demo")
circ_ref = qnx.circuits.upload(circuit=Circuit(2).H(0).CX(0, 1).measure_all(),
                               name="bell", project=project)

config = qnx.QuantinuumConfig(device_name="H2-1LE")   # SAFE default: noiseless, FREE
compiled = qnx.compile(programs=[circ_ref], backend_config=config,
                       name="compile-bell", project=project)[0]

exec_job = qnx.start_execute_job(programs=[compiled], n_shots=[100],
                                 backend_config=config, name="exec-bell",
                                 project=project, max_cost=5.0)   # HQC ceiling guardrail

qnx.jobs.wait_for(exec_job)
counts = qnx.jobs.results(exec_job)[0].download_result().get_counts()
```

## Verify before wiring (do not invent)

1. **`login_no_interaction`** is `qnx.auth.login_no_interaction` (not top-level); `login_with_token` *is*
   top-level. The docs API index is stale vs code.
2. **Confirm the exact free-emulator string live** (`H2-1LE`) on the event's account before defaulting to it.
3. Confirm signatures of `CircuitRef.download_circuit()`, `CompilationResultRef.get_output()`,
   `ExecutionResultRef.download_result()` before wiring the results tool.
4. Confirm `qnx.circuits.cost()` behavior (blocking free `H2-1SC` job) on the real account.
5. Treat any credential/roles/teams create/delete as W/X — those modules were only partially read (and are
   out of scope anyway, see `../DESIGN.md` §2).

## Sources (observed 2026-07-20)
- `Quantinuum/qnexus` at tag `v0.46.0` — `qnexus/__init__.py`, `config.py`, `client/{auth,projects,circuits,devices,quotas,credentials,results}.py`, `client/jobs/{__init__,_compile,_execute}.py`, `models/__init__.py` (via `gh api …/contents/…?ref=30244a2e…`).
- docs.quantinuum.com/nexus: getting-started, devices API, qnexus API index, backend configs; systems H2 emulators (HQC consumption); Selene-in-Nexus.
