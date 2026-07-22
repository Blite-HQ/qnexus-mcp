"""Pure result-shaping: top-N outcome truncation with explicit metadata (audit finding #1)."""

from qnexus_mcp.results import shape_result, truncate_counts


def test_truncate_returns_all_counts_when_under_limit():
    counts = {"00": 51, "11": 49}
    out = truncate_counts(counts, limit=100)
    assert out["counts"] == counts


def test_truncate_keeps_top_n_by_frequency():
    counts = {"00": 5, "01": 40, "10": 30, "11": 25}
    out = truncate_counts(counts, limit=2)
    assert out["counts"] == {"01": 40, "10": 30}


def test_truncate_breaks_frequency_ties_by_bitstring_ascending():
    counts = {"11": 10, "00": 10, "10": 10, "01": 10}
    out = truncate_counts(counts, limit=2)
    assert list(out["counts"]) == ["00", "01"]


def test_truncate_metadata_reports_total_omitted_outcomes_and_shots():
    counts = {"00": 5, "01": 40, "10": 30, "11": 25}
    out = truncate_counts(counts, limit=2)
    assert out["total_outcomes"] == 4
    assert out["omitted_outcomes"] == 2
    assert out["omitted_shots"] == 30  # 25 + 5


def test_truncate_metadata_zeros_when_nothing_omitted():
    out = truncate_counts({"00": 51, "11": 49}, limit=100)
    assert out["total_outcomes"] == 2
    assert out["omitted_outcomes"] == 0
    assert out["omitted_shots"] == 0


def test_shape_result_single_item_keeps_id_and_counts_keys():
    out = shape_result("j1", [{"00": 51, "11": 49}], limit=100)
    assert out["id"] == "j1"
    assert out["counts"] == {"00": 51, "11": 49}
    assert "items" not in out


def test_shape_result_multi_item_returns_indexed_items_with_metadata():
    out = shape_result("j1", [{"00": 10}, {"11": 20}], limit=100)
    assert out["id"] == "j1"
    assert out["n_items"] == 2
    assert out["items"][0] == {
        "index": 0,
        "counts": {"00": 10},
        "total_outcomes": 1,
        "omitted_outcomes": 0,
        "omitted_shots": 0,
    }
    assert out["items"][1]["index"] == 1
    assert out["items"][1]["counts"] == {"11": 20}
