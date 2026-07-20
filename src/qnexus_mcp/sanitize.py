"""Redact secret-shaped values before anything reaches the LLM, logs, or disk."""

from __future__ import annotations

from typing import Any

_SECRET_HINTS = ("token", "secret", "password", "cookie", "authorization", "credential", "myqos")


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(hint in k for hint in _SECRET_HINTS)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if _is_secret_key(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    return value
