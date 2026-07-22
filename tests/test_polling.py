"""Deterministic tests for the tool-layer poll loop (injectable clock/sleep, recorded reports)."""

import pytest
from fastmcp.exceptions import ToolError

from qnexus_mcp.polling import poll_job


class _Env:
    """Fake time: sleeping advances the clock; every status/report call is recorded."""

    def __init__(self, statuses):
        self.t = 0.0
        self.sleeps = []
        self.reports = []
        self._statuses = iter(statuses)

    def clock(self):
        return self.t

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds

    async def report(self, progress, total, message):
        self.reports.append((progress, total, message))

    async def status_fn(self):
        return next(self._statuses)


def _poll(env, timeout=300.0, **kwargs):
    return poll_job(
        env.status_fn,
        job_id="j1",
        timeout=timeout,
        report=env.report,
        sleep=env.sleep,
        clock=env.clock,
        **kwargs,
    )


async def test_poll_returns_final_status_when_completed():
    env = _Env([{"status": "QUEUED"}, {"status": "RUNNING"}, {"status": "COMPLETED"}])
    out = await _poll(env)
    assert out["status"] == "COMPLETED"
    assert len(env.sleeps) == 2  # slept between polls, not after the terminal one


async def test_poll_reports_progress_with_status_and_queue_position_each_iteration():
    env = _Env([{"status": "QUEUED", "queue_position": 3}, {"status": "COMPLETED"}])
    await _poll(env, timeout=60.0)
    assert len(env.reports) == 2
    progress, total, message = env.reports[0]
    assert total == 60.0
    assert "QUEUED" in message and "3" in message


async def test_poll_backoff_grows_by_factor_to_cap():
    env = _Env([{"status": "QUEUED"}] * 8 + [{"status": "COMPLETED"}])
    await _poll(env, timeout=300.0, initial=2.0, factor=1.5, cap=15.0)
    assert env.sleeps == [2.0, 3.0, 4.5, 6.75, 10.125, 15.0, 15.0, 15.0]


async def test_poll_sleep_never_exceeds_remaining_timeout():
    env = _Env([{"status": "QUEUED"}] * 3)
    with pytest.raises(ToolError, match="Timed out after 5.0s"):
        await _poll(env, timeout=5.0, initial=4.0, factor=1.5, cap=15.0)
    assert env.sleeps == [4.0, 1.0]  # second sleep clamped to the remaining second


async def test_poll_raises_tool_error_on_error_status_with_message():
    env = _Env([{"status": "ERROR", "message": "compilation exploded"}])
    with pytest.raises(ToolError, match="compilation exploded"):
        await _poll(env)


@pytest.mark.parametrize("status", ["CANCELLED", "TERMINATED", "DEPLETED"])
async def test_poll_raises_tool_error_on_terminal_failure(status):
    env = _Env([{"status": status}])
    with pytest.raises(ToolError, match=status):
        await _poll(env)


@pytest.mark.parametrize("status", ["CANCELLING", "RETRYING"])
async def test_poll_keeps_polling_through_transient_states(status):
    env = _Env([{"status": status}, {"status": "COMPLETED"}])
    out = await _poll(env)
    assert out["status"] == "COMPLETED"


async def test_poll_timeout_message_says_job_still_running_do_not_resubmit():
    env = _Env([{"status": "RUNNING"}] * 5)
    with pytest.raises(ToolError, match="still running") as exc:
        await _poll(env, timeout=3.0, initial=2.0)
    assert "Do not resubmit" in str(exc.value)
    assert "nexus_job_status" in str(exc.value)
