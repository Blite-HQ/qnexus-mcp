import types

import pytest

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.context import bind_state, rate_limiter_of
from qnexus_mcp.guards import RateLimited, SpendDenied, SpendGuard, SubmitRateLimiter


async def _yes(_msg):
    return True


async def _no(_msg):
    return False


async def test_free_emulator_needs_no_spend_flag():
    g = SpendGuard(ServerConfig())  # read-only defaults, allow_spend False
    await g.check_and_confirm(device="H2-1LE", estimated_cost=0.0, confirm=_yes)  # no raise


async def test_billable_denied_without_allow_spend():
    g = SpendGuard(ServerConfig(toolsets=frozenset({"read", "execute"})))
    with pytest.raises(SpendDenied, match="allow-spend"):
        await g.check_and_confirm(device="H2-1E", estimated_cost=3.0, confirm=_yes)


async def test_billable_denied_over_max_credits():
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=2.0)
    g = SpendGuard(cfg)
    with pytest.raises(SpendDenied, match="max-credits"):
        await g.check_and_confirm(device="H2-1E", estimated_cost=5.0, confirm=_yes)


async def test_billable_requires_confirmation():
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    g = SpendGuard(cfg)
    with pytest.raises(SpendDenied, match="not confirmed"):
        await g.check_and_confirm(device="H2-1E", estimated_cost=5.0, confirm=_no)
    await g.check_and_confirm(device="H2-1E", estimated_cost=5.0, confirm=_yes)  # ok


async def test_hardware_needs_allow_hardware():
    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    g = SpendGuard(cfg)
    with pytest.raises(SpendDenied, match="allow-hardware"):
        await g.check_and_confirm(device="H2-1", estimated_cost=1.0, confirm=_yes)


def test_hardware_precheck_reports_both_missing_flags_at_once():
    # Restarting the server once with the full set beats discovering a second missing flag
    # only after fixing the first and retrying (found via an independent-agent test).
    g = SpendGuard(ServerConfig(toolsets=frozenset({"read", "execute"})))
    with pytest.raises(SpendDenied, match="allow-spend") as exc:
        g.precheck("H1-1")
    assert "allow-hardware" in str(exc.value)


def test_idempotency_key_is_stable():
    g = SpendGuard(ServerConfig())
    assert g.idempotency_key({"b": 2, "a": 1}) == g.idempotency_key({"a": 1, "b": 2})


async def test_confirmation_message_uses_custom_action():
    messages = []

    async def confirm(msg):
        messages.append(msg)
        return True

    cfg = ServerConfig(toolsets=frozenset({"read", "execute"}), allow_spend=True, max_credits=10.0)
    await SpendGuard(cfg).check_and_confirm(
        device="H2-1E",
        estimated_cost=5.0,
        confirm=confirm,
        action="Submit 3 circuits x 10 shots to H2-1E as one batch job?",
    )
    assert "3 circuits" in messages[0]
    assert "ceiling 10.0" in messages[0]


# --- batch-aware, configurable rate limiting --------------------------------------------------


def test_rate_limiter_batch_consumes_count_slots():
    limiter = SubmitRateLimiter(max_per_minute=6, now=lambda: 0.0)
    limiter.check(count=5)
    limiter.check()  # sixth slot still free
    with pytest.raises(RateLimited):
        limiter.check()


def test_rate_limiter_rejects_batch_exceeding_remaining_capacity_without_recording():
    limiter = SubmitRateLimiter(max_per_minute=6, now=lambda: 0.0)
    limiter.check(count=4)
    with pytest.raises(RateLimited, match="4 used"):
        limiter.check(count=3)  # only 2 slots left
    limiter.check(count=2)  # the rejected batch must not have consumed anything


def test_rate_limited_message_states_capacity_and_flag():
    limiter = SubmitRateLimiter(max_per_minute=1, now=lambda: 0.0)
    limiter.check()
    with pytest.raises(RateLimited, match="max-submissions-per-minute") as exc:
        limiter.check()
    assert "1" in str(exc.value)


def test_batch_larger_than_cap_gets_split_guidance_not_wait_advice():
    # Review finding: with count > max the old message said "wait", which can never succeed.
    limiter = SubmitRateLimiter(max_per_minute=6, now=lambda: 0.0)
    with pytest.raises(RateLimited) as exc:
        limiter.check(count=7)
    message = str(exc.value)
    assert "Split" in message and "6" in message
    assert "Wait before submitting again" not in message
    limiter.check(count=6)  # the rejected oversized batch consumed nothing


def test_bind_state_builds_limiter_from_config(fake_client):
    server = types.SimpleNamespace()
    bind_state(server, fake_client, ServerConfig(max_submissions_per_minute=2))
    limiter = rate_limiter_of(types.SimpleNamespace(fastmcp=server))
    limiter.check(count=2)
    with pytest.raises(RateLimited):
        limiter.check()
