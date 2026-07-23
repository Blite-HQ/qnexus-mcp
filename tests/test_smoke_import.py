def test_package_imports_and_reports_version():
    # Compare against the installed metadata, not a hardcoded literal: a literal breaks on
    # every `cz bump` (found live: the v0.2.0 bump turned CI red on this line).
    from importlib.metadata import version

    import qnexus_mcp

    assert qnexus_mcp.__version__ == version("qnexus-mcp")
