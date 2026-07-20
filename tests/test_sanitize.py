from qnexus_mcp.sanitize import redact


def test_redacts_secret_keys_recursively():
    data = {"user": "a", "token": "xyz", "nested": {"access_token": "q", "id": 1}}
    out = redact(data)
    assert out["user"] == "a" and out["nested"]["id"] == 1
    assert out["token"] == "***" and out["nested"]["access_token"] == "***"


def test_passes_through_non_dicts():
    assert redact([1, 2]) == [1, 2]
    assert redact("plain") == "plain"
