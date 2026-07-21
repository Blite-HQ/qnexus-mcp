"""Server-side spend/destructive guards. The real controls — annotations are only UX hints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .backends import is_billable, is_hardware
from .config import ServerConfig

Confirm = Callable[[str], Awaitable[bool]]


class SpendDenied(Exception):
    """Raised when a spend / hardware / confirmation guard blocks an action."""


class SpendGuard:
    def __init__(self, config: ServerConfig) -> None:
        self._config = config

    async def check_and_confirm(
        self, *, device: str, estimated_cost: float, confirm: Confirm
    ) -> None:
        """Allow, or raise SpendDenied. Free devices (H2-1LE / *-1SC) pass with no gate."""
        if not is_billable(device):
            return
        c = self._config
        if not c.allow_spend:
            raise SpendDenied(f"{device} spends credits; start the server with --allow-spend")
        if is_hardware(device) and not c.allow_hardware:
            raise SpendDenied(f"{device} is real hardware; requires --allow-hardware")
        if estimated_cost > c.max_credits:
            raise SpendDenied(
                f"estimated {estimated_cost} HQC exceeds --max-credits={c.max_credits}"
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
