import pytest

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.guards import SpendDenied, SpendGuard


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


def test_idempotency_key_is_stable():
    g = SpendGuard(ServerConfig())
    assert g.idempotency_key({"b": 2, "a": 1}) == g.idempotency_key({"a": 1, "b": 2})
