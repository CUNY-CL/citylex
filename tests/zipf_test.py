import pytest

from citylex import zipf


@pytest.mark.parametrize(
    "count,total,expected",
    [
        # Threshold values per million words.
        (0, 1_000_000, 0.0),
        (0.01, 1_000_000, 1.0),
        (0.1, 1_000_000, 2.0),
        (1, 1_000_000, 3.0),
        (10, 1_000_000, 4.0),
        (100, 1_000_000, 5.0),
        (1_000, 1_000_000, 6.0),
        (10_000, 1_000_000, 7.0),
    ],
)
def test_zipf(count, total, expected):
    assert zipf.zipf_scale(count, total) == expected
