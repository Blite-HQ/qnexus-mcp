"""Redact secret-shaped keys AND values before anything reaches the LLM, logs, or disk."""

from __future__ import annotations

import re
from typing import Any

_MASK = "***"

# Redact a dict entry if its key name contains any of these.
_SECRET_KEY_HINTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "cookie",
    "authorization",
    "credential",
    "apikey",
    "api_key",
    "bearer",
    "jwt",
    "refresh",
    "signature",
    "private",
    "myqos",
)

# Redact a string VALUE if it looks like a secret: a JWT, a Bearer prefix, or a myqos cookie.
_SECRET_VALUE_RE = re.compile(
    r"(eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,})"  # JWT
    r"|(bearer\s+\S+)"  # Bearer <token>
    r"|(myqos\w*)",  # Quantinuum session cookies
    re.IGNORECASE,
)


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(hint in k for hint in _SECRET_KEY_HINTS)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (_MASK if _is_secret_key(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    if isinstance(value, str):
        return _MASK if _SECRET_VALUE_RE.search(value) else value
    return value
