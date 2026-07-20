import pytest
from pydantic import ValidationError

from qnexus_mcp.config import DEFAULT_TOOLSETS, ServerConfig, config_from_sources


def test_defaults_are_read_only_strict():
    c = ServerConfig()
    assert c.toolsets == DEFAULT_TOOLSETS == frozenset({"read"})
    assert c.allow_spend is False and c.allow_hardware is False
    assert c.allow_destructive is False and c.max_credits == 0.0
    assert c.projects is None


def test_unknown_toolset_rejected():
    with pytest.raises(ValidationError):
        ServerConfig(toolsets=frozenset({"read", "bogus"}))


def test_cli_enables_execute_and_spend():
    c = config_from_sources(
        ["--toolsets", "read,execute", "--allow-spend", "--max-credits", "5"], env={}
    )
    assert c.toolsets == frozenset({"read", "execute"})
    assert c.allow_spend is True and c.max_credits == 5.0


def test_env_is_fallback_when_flag_absent():
    c = config_from_sources([], env={"QNEXUS_MCP_TOOLSETS": "read,execute"})
    assert c.toolsets == frozenset({"read", "execute"})


def test_cli_overrides_env():
    c = config_from_sources(["--toolsets", "read"], env={"QNEXUS_MCP_TOOLSETS": "read,execute"})
    assert c.toolsets == frozenset({"read"})
