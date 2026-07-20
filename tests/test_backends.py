import pytest

from qnexus_mcp.backends import DEFAULT_DEVICE, is_billable, is_hardware


@pytest.mark.parametrize(
    "name,billable",
    [
        ("H2-1LE", False),
        ("H1-1LE", False),
        ("H2-1SC", False),
        ("H2-1E", True),
        ("H1-1E", True),
        ("H2-1", True),
        ("H1-1", True),
    ],
)
def test_billable_classification(name, billable):
    assert is_billable(name) is billable


def test_default_device_is_free_emulator():
    assert DEFAULT_DEVICE == "H2-1LE"
    assert is_billable(DEFAULT_DEVICE) is False
    assert is_hardware(DEFAULT_DEVICE) is False


def test_hardware_detection():
    assert is_hardware("H2-1") is True
    assert is_hardware("H2-1E") is False
