from qnexus_mcp.client import NexusClient


def test_fake_client_satisfies_protocol(fake_client):
    assert isinstance(fake_client, NexusClient)


def test_auth_status_shape(fake_client):
    s = fake_client.auth_status()
    assert set(s) == {"logged_in", "hint"}
    assert s["logged_in"] is True
