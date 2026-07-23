"""Classify Quantinuum device strings by cost/danger.

Verified against qnexus v0.46.0 docstrings (see docs/research/04-qnexus-sdk-surface.md):
  *-1LE = noiseless emulator (FREE, 0 HQC);  *-1SC = syntax checker (FREE);
  *-1E  = noisy emulator (SPENDS HQC);        *-1  = real hardware (SPENDS HQC).
The exact free-emulator string is re-verified live before the execute path is trusted (M1.9/M2.2).
"""

from __future__ import annotations

DEFAULT_DEVICE = "H2-1LE"

# Explicit allowlist of known FREE devices. Everything else fails SAFE (treated as billable), so a
# future billable device whose name happens to end in LE/SC can never silently skip the SpendGuard.
FREE_DEVICES = frozenset({"H2-1LE", "H1-1LE", "H2-1SC", "H1-1SC"})


def is_billable(device_name: str) -> bool:
    return device_name.upper() not in FREE_DEVICES


def is_hardware(device_name: str) -> bool:
    # Real QPUs are billable and not emulators (no trailing 'E'). Unknown billable names default to
    # hardware, so they require --allow-hardware (the more restrictive gate).
    return is_billable(device_name) and not device_name.upper().endswith("E")


def syntax_checker_for(device_name: str) -> str:
    """Map a device to its family's syntax-checker device (H2-1 / H2-1E / H2-1LE -> H2-1SC).

    Always pass this explicitly to qnx.circuits.cost: qnexus 0.46 derives the checker itself with
    a `str.strip("E")` whose result is discarded, yielding invalid names like "H2-1LESC" (found
    live: cost estimation failed for every non-SC device name).
    """
    base = device_name.upper()
    if base.endswith("SC"):
        return base
    if base.endswith("LE"):
        base = base[:-2]
    elif base.endswith("E"):
        base = base[:-1]
    return base + "SC"
