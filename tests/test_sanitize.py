from qnexus_mcp.sanitize import redact


def test_redacts_secret_keys_recursively():
    data = {"user": "a", "token": "xyz", "nested": {"access_token": "q", "id": 1}}
    out = redact(data)
    assert out["user"] == "a" and out["nested"]["id"] == 1
    assert out["token"] == "***" and out["nested"]["access_token"] == "***"


def test_passes_through_non_dicts():
    assert redact([1, 2]) == [1, 2]
    assert redact("plain") == "plain"


def test_redacts_secret_value_shapes():
    out = redact(
        {
            "jwt_in_value": "eyJhbGciOiJI.eyJzdWIiXX",
            "header": "Bearer abc123def",
            "cookie_val": "myqos_oat_session",
        }
    )
    assert out["jwt_in_value"] == "***"
    assert out["header"] == "***"
    assert out["cookie_val"] == "***"


def test_redacts_api_key_and_signature_keys():
    out = redact({"api_key": "abc", "signature": "xyz", "device": "H2-1LE"})
    assert out["api_key"] == "***"
    assert out["signature"] == "***"
    assert out["device"] == "H2-1LE"
