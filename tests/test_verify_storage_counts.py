import pytest

from scripts.verify_storage_counts import assert_counts


def test_storage_count_invariant_reports_exact_mismatches():
    assert_counts("store", {"jobs": 2}, {"jobs": 2})
    with pytest.raises(AssertionError, match='"expected": 2'):
        assert_counts("store", {"jobs": 1}, {"jobs": 2})
