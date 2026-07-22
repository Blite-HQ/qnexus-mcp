"""Pure result-shaping helpers: top-N outcome truncation with explicit metadata.

A noisy or many-qubit job can produce tens of thousands of distinct bitstrings; returned raw,
that floods the agent's context (audit finding). Tools cap the counts at `--max-outcomes` via
these helpers. Truncation is presentation policy, so it lives here (tool layer), never in the
client: the client always returns full raw data.
"""

from __future__ import annotations

from typing import Any


def truncate_counts(counts: dict[str, int], limit: int) -> dict[str, Any]:
    """Keep the top-`limit` outcomes by count (ties broken by bitstring ascending).

    Metadata is always present -- zeros when nothing was omitted -- so the shape is stable:
    {"counts", "total_outcomes", "omitted_outcomes", "omitted_shots"}.
    """
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    omitted = ordered[limit:]
    return {
        "counts": dict(ordered[:limit]),
        "total_outcomes": len(counts),
        "omitted_outcomes": len(omitted),
        "omitted_shots": sum(count for _, count in omitted),
    }


def shape_result(job_id: str, counts_list: list[dict[str, int]], limit: int) -> dict[str, Any]:
    """Shape a job's per-item counts for the agent.

    Single-item jobs (the common case) keep the flat {"id", "counts", ...} shape; multi-item
    (batch) jobs return one entry per circuit under "items", in submission order.
    """
    shaped = [truncate_counts(counts, limit) for counts in counts_list]
    if len(shaped) == 1:
        return {"id": job_id, **shaped[0]}
    return {
        "id": job_id,
        "n_items": len(shaped),
        "items": [{"index": i, **item} for i, item in enumerate(shaped)],
    }
