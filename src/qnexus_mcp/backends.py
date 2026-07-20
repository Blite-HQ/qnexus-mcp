"""Classify Quantinuum device strings by cost/danger.

Verified against qnexus v0.46.0 docstrings (see docs/research/04-qnexus-sdk-surface.md):
  *-1LE = noiseless emulator (FREE, 0 HQC);  *-1SC = syntax checker (FREE);
  *-1E  = noisy emulator (SPENDS HQC);        *-1  = real hardware (SPENDS HQC).
The exact free-emulator string is re-verified live before the execute path is trusted (M1.9/M2.2).
"""

from __future__ import annotations

DEFAULT_DEVICE = "H2-1LE"


def is_hardware(device_name: str) -> bool:
    name = device_name.upper()
    return not (name.endswith("LE") or name.endswith("SC") or name.endswith("E"))


def is_billable(device_name: str) -> bool:
    name = device_name.upper()
    if name.endswith("LE") or name.endswith("SC"):
        return False
    return name.endswith("E") or is_hardware(name)
