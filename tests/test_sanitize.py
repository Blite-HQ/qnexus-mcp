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


# --- broadened value shapes (defense in depth: values under non-secret keys) ------------------


def test_redacts_github_classic_and_fine_grained_tokens():
    out = redact(
        {
            "msg": "push failed for ghp_abcdefghijklmnopqrst1234",
            "msg2": "using github_pat_11ABCDEFG_abcdefghijklmnop",
        }
    )
    assert out["msg"] == "***"
    assert out["msg2"] == "***"


def test_redacts_slack_xox_tokens():
    assert redact("error from xoxb-123456789012-abcdefghijkl") == "***"


def test_redacts_sk_prefixed_api_keys():
    assert redact("sk-abcdefghijklmnopqrstuvwx") == "***"
    assert redact("sk_live_abcdefghijklmnop") == "***"


def test_redacts_aws_access_key_id():
    assert redact("AKIAIOSFODNN7EXAMPLE") == "***"


def test_redacts_secretish_key_value_pair_inside_string():
    assert redact("rejected: api_key=hunter2secret is invalid") == "***"
    assert redact("config had token: abcd1234efgh") == "***"


def test_keeps_bitstring_count_keys_and_values():
    counts = {"01010101010101010101": 12, "00000000000000000000": 88}
    assert redact(counts) == counts
    assert redact("0101010101010101010101010101") == "0101010101010101010101010101"


def test_keeps_uuids():
    u = "123e4567-e89b-12d3-a456-426614174000"
    assert redact(u) == u


def test_keeps_qasm_source_text():
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nrz(0.5) q[0];\n'
    assert redact(qasm) == qasm


def test_keeps_short_sk_prefixed_words():
    assert redact("sk-limit") == "sk-limit"
