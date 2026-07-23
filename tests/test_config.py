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


def test_read_is_forced_on_even_if_excluded():
    c = config_from_sources(["--toolsets", "execute"], env={})
    assert "read" in c.toolsets and "execute" in c.toolsets


def test_help_flag_exits_cleanly_instead_of_being_swallowed():
    # Windows-testing finding: add_help=False silently ate --help.
    with pytest.raises(SystemExit) as exc:
        config_from_sources(["--help"], env={})
    assert exc.value.code == 0


def test_unknown_flag_is_rejected_not_silently_ignored(capsys):
    # Windows-testing finding (HIGH): parse_known_args silently dropped typos, so
    # `--project sandbox` (missing the s) launched with NO allowlist at all -- fail-open.
    with pytest.raises(SystemExit) as exc:
        config_from_sources(["--project", "sandbox"], env={})
    assert exc.value.code != 0
    assert "unrecognized" in capsys.readouterr().err


def test_bad_max_credits_env_raises():
    with pytest.raises(ValueError, match="must be a number"):
        config_from_sources([], env={"QNEXUS_MCP_MAX_CREDITS": "abc"})


def test_negative_max_credits_rejected():
    with pytest.raises(ValidationError):
        ServerConfig(max_credits=-1.0)


def test_response_and_rate_limit_defaults():
    c = ServerConfig()
    assert c.max_outcomes == 100
    assert c.max_submissions_per_minute == 6


def test_max_outcomes_cli_overrides_env():
    c = config_from_sources(["--max-outcomes", "50"], env={"QNEXUS_MCP_MAX_OUTCOMES": "200"})
    assert c.max_outcomes == 50


def test_max_outcomes_env_fallback():
    c = config_from_sources([], env={"QNEXUS_MCP_MAX_OUTCOMES": "200"})
    assert c.max_outcomes == 200


def test_max_outcomes_rejects_non_positive():
    with pytest.raises(ValidationError):
        ServerConfig(max_outcomes=0)


def test_bad_max_outcomes_env_raises():
    with pytest.raises(ValueError, match="must be an integer"):
        config_from_sources([], env={"QNEXUS_MCP_MAX_OUTCOMES": "many"})


def test_max_submissions_per_minute_cli_overrides_env():
    c = config_from_sources(
        ["--max-submissions-per-minute", "30"],
        env={"QNEXUS_MCP_MAX_SUBMISSIONS_PER_MINUTE": "12"},
    )
    assert c.max_submissions_per_minute == 30


def test_max_submissions_per_minute_env_fallback():
    c = config_from_sources([], env={"QNEXUS_MCP_MAX_SUBMISSIONS_PER_MINUTE": "12"})
    assert c.max_submissions_per_minute == 12


def test_max_submissions_per_minute_rejects_non_positive():
    with pytest.raises(ValidationError):
        ServerConfig(max_submissions_per_minute=0)


def test_bad_max_submissions_per_minute_env_raises():
    with pytest.raises(ValueError, match="must be an integer"):
        config_from_sources([], env={"QNEXUS_MCP_MAX_SUBMISSIONS_PER_MINUTE": "lots"})


def test_projects_allowlist_parsed_from_cli_and_env():
    c = config_from_sources(["--projects", "sandbox,demo"], env={})
    assert c.projects == frozenset({"sandbox", "demo"})
    c = config_from_sources([], env={"QNEXUS_MCP_PROJECTS": "sandbox"})
    assert c.projects == frozenset({"sandbox"})
    assert config_from_sources([], env={}).projects is None
