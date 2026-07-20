"""Read-only tools (always available). Each wraps one NexusClient method."""

from __future__ import annotations

from typing import Any

from ..client import NexusClient
from ..config import ServerConfig
from ..permissions import ToolSpec


def _read(name: str, method: str, description: str, idempotent: bool = True) -> ToolSpec:
    def handler(client: NexusClient, config: ServerConfig, ctx: Any, **kwargs: Any) -> Any:
        return getattr(client, method)(**kwargs)

    return ToolSpec(
        name=name,
        toolset="read",
        handler=handler,
        read_only=True,
        idempotent=idempotent,
        description=description,
    )


READ_SPECS: list[ToolSpec] = [
    _read("nexus_auth_status", "auth_status", "Report whether a valid Nexus session exists."),
    _read("nexus_whoami", "whoami", "Return the authenticated Nexus user."),
    _read("nexus_list_devices", "list_devices", "List available backends and their status."),
    _read("nexus_list_projects", "list_projects", "List Nexus projects visible to the user."),
    _read("nexus_get_quota", "get_quota", "Return remaining compilation/simulation quotas."),
    _read("nexus_list_jobs", "list_jobs", "List jobs, optionally filtered by project/status."),
    _read("nexus_job_status", "job_status", "Return the status of a job by id."),
    _read("nexus_job_cost", "job_cost", "Return the HQC cost of an existing job."),
    _read("nexus_get_results", "get_results", "Return counts/results for a completed job."),
]
