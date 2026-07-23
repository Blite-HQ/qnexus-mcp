import pytest

from qnexus_mcp.backends import DEFAULT_DEVICE, is_billable, is_hardware, syntax_checker_for


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


@pytest.mark.parametrize(
    "device,checker",
    [
        ("H2-1", "H2-1SC"),  # hardware
        ("H2-1E", "H2-1SC"),  # noisy emulator
        ("H2-1LE", "H2-1SC"),  # noiseless emulator
        ("H2-1SC", "H2-1SC"),  # already a syntax checker
        ("H1-1E", "H1-1SC"),  # other family, same rule
    ],
)
def test_syntax_checker_for_maps_device_to_family_checker(device, checker):
    # Found live (Windows E2E test): qnexus 0.46's circuits.cost derives the checker with a
    # str.strip("E") whose result is DISCARDED, producing invalid names like "H2-1LESC".
    # We must always pass the checker explicitly.
    assert syntax_checker_for(device) == checker
