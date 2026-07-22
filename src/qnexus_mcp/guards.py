"""Server-side spend/destructive guards (the real controls; annotations are only UX hints)."""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError

from .backends import is_billable, is_hardware
from .config import DEFAULT_PROJECT, ServerConfig

Confirm = Callable[[str], Awaitable[bool]]
QuotaCheck = Callable[[str], Awaitable[bool]]


class SpendDenied(ToolError):
    """Blocks a spend/hardware action. Subclasses ToolError so its message reaches the agent."""


class ConfirmationDenied(ToolError):
    """A destructive/spend action was not confirmed. ToolError so its message reaches the agent."""


class RateLimited(ToolError):
    """Too many submissions in a short window. ToolError so its message reaches the agent."""


class ProjectDenied(ToolError):
    """The target project is outside the launch allowlist (--projects)."""


def check_project_allowed(config: ServerConfig, project: str | None) -> None:
    """Enforce the --projects allowlist on all mutating tools. None target = the default project."""
    if config.projects is None:
        return
    effective = project or DEFAULT_PROJECT
    if effective not in config.projects:
        raise ProjectDenied(
            f"project '{effective}' is not in the launch allowlist (--projects="
            f"{','.join(sorted(config.projects))}). Nothing was changed."
        )


class SubmitRateLimiter:
    """Sliding-window cap on circuit submissions (free lane included) to bound queue pressure.

    Billable submissions are additionally throttled by the mandatory confirmation; this limiter is
    the backstop for the free lane, where no confirmation is required.
    """

    def __init__(self, max_per_minute: int = 6, now: Callable[[], float] = time.monotonic) -> None:
        self._max = max_per_minute
        self._now = now
        self._stamps: deque[float] = deque()

    def check(self, count: int = 1) -> None:
        """Consume `count` submission slots (a batch of N circuits consumes N), or raise.

        A rejected call consumes nothing, so a too-large batch can be retried smaller (or later)
        without having burned capacity.
        """
        t = self._now()
        while self._stamps and t - self._stamps[0] > 60.0:
            self._stamps.popleft()
        if len(self._stamps) + count > self._max:
            raise RateLimited(
                f"Rate limit: at most {self._max} submissions per minute "
                f"({len(self._stamps)} used, {count} requested). Wait before submitting again; "
                "do not retry in a loop. The operator can raise the cap by restarting with "
                "--max-submissions-per-minute."
            )
        self._stamps.extend([t] * count)


class SpendGuard:
    def __init__(self, config: ServerConfig) -> None:
        self._config = config

    def precheck(self, device: str) -> None:
        """Cheap flag-only gate. Called BEFORE any cost estimate so a denied device never even
        enqueues the (free) estimation job. Raises SpendDenied, or returns for free devices.

        Reports every missing flag at once (not just the first) -- so restarting the server once
        with the full set is enough, instead of discovering a second missing flag only after
        fixing the first and retrying.
        """
        if not is_billable(device):
            return
        c = self._config
        missing = []
        if not c.allow_spend:
            missing.append("--allow-spend")
        if is_hardware(device) and not c.allow_hardware:
            missing.append("--allow-hardware")
        if missing:
            raise SpendDenied(
                f"{device} requires the server to be restarted with: {', '.join(missing)}. "
                "This cannot be enabled from a tool call."
            )

    async def check_and_confirm(
        self,
        *,
        device: str,
        estimated_cost: float,
        confirm: Confirm,
        quota_check: QuotaCheck | None = None,
    ) -> None:
        """Allow, or raise SpendDenied. Free devices (H2-1LE / *-1SC) pass with no gate.

        For billable emulators the "simulation" quota is pre-checked (when a checker is supplied).
        Real hardware has no balance-check API in the qnexus SDK, so the ceiling + confirmation are
        the only pre-submission guards there.
        """
        if not is_billable(device):
            return
        self.precheck(device)
        c = self._config
        if estimated_cost > c.max_credits:
            raise SpendDenied(
                f"estimated {estimated_cost} HQC exceeds --max-credits={c.max_credits}"
            )
        if (
            quota_check is not None
            and not is_hardware(device)
            and not await quota_check("simulation")
        ):
            raise SpendDenied(
                "the Nexus 'simulation' quota is exhausted or unavailable for this account; "
                "refusing to submit to a billable emulator"
            )
        approved = await confirm(
            f"Submit to {device}? Estimated cost: {estimated_cost} HQC "
            f"(ceiling {c.max_credits}). This spends real credits."
        )
        if not approved:
            raise SpendDenied("submission not confirmed by the user")

    @staticmethod
    def idempotency_key(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()
