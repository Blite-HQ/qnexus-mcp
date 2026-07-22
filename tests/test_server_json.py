import json
from pathlib import Path

SERVER_JSON = json.loads((Path(__file__).parent.parent / "server.json").read_text())


def test_description_fits_the_registry_limit():
    # The MCP Registry rejects the whole publish with a 422 if this exceeds 100 chars
    # (found live: v0.1.0's first publish attempt failed on exactly this).
    assert len(SERVER_JSON["description"]) <= 100


def test_version_matches_package_version():
    import qnexus_mcp

    assert SERVER_JSON["version"] == qnexus_mcp.__version__
    assert SERVER_JSON["packages"][0]["version"] == qnexus_mcp.__version__
