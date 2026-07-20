"""
tests/test_aggregate_math.py
Tests that aggregate_results.py arithmetic is correct.
Uses in-memory DataFrames — no file I/O.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import pytest

from aggregate_results import compute_breakdown, _rate, overlap


class TestComputeBreakdown:
    def _make_df(self, buckets: list[str]) -> pd.DataFrame:
        return pd.DataFrame({"bucket": buckets, "swear_count": [0] * len(buckets)})

    def test_counts_sum_to_n(self):
        df = self._make_df(["racial_ethnic_flagged", "nationality_flagged", "unflagged", "model_unsupported"])
        rec = compute_breakdown(df)
        assert rec["n"] == 4
        assert (
            rec["racial_ethnic_flagged_n"]
            + rec["nationality_flagged_n"]
            + rec["unflagged_n"]
            + rec["model_unsupported_n"]
        ) == 4

    def test_all_unflagged(self):
        df = self._make_df(["unflagged"] * 100)
        rec = compute_breakdown(df)
        assert rec["any_flagged_n"] == 0
        assert rec["any_flagged_rate"] == 0.0
        assert rec["unflagged_n"] == 100

    def test_all_racial_ethnic(self):
        df = self._make_df(["racial_ethnic_flagged"] * 50)
        rec = compute_breakdown(df)
        assert rec["racial_ethnic_flagged_n"] == 50
        assert rec["racial_ethnic_rate"] == 1.0
        assert rec["any_flagged_n"] == 50

    def test_zero_division_safe(self):
        df = self._make_df([])
        rec = compute_breakdown(df)
        assert rec["n"] == 0
        assert rec["any_flagged_rate"] == 0.0

    def test_model_unsupported_not_counted_as_flagged(self):
        df = self._make_df(["model_unsupported"] * 10)
        rec = compute_breakdown(df)
        assert rec["any_flagged_n"] == 0
        assert rec["model_unsupported_n"] == 10


class TestRate:
    def test_normal(self):
        assert _rate(50, 100) == 0.5

    def test_zero_denominator(self):
        assert _rate(0, 0) == 0.0

    def test_precision(self):
        # Should round to 6 decimal places
        r = _rate(1, 3)
        assert r == round(1 / 3, 6)


class TestOverlap:
    def test_four_cells_sum_to_total(self):
        df = pd.DataFrame(
            {
                "bucket": ["racial_ethnic_flagged", "unflagged", "nationality_flagged", "unflagged"],
                "swear_count": [1, 0, 0, 2],
            }
        )
        result = overlap(df)
        assert result["n"].sum() == len(df)

    def test_group_keys_are_unique(self):
        df = pd.DataFrame(
            {"bucket": ["unflagged"] * 5, "swear_count": [0, 0, 1, 0, 1]}
        )
        result = overlap(df)
        assert len(result["group"].unique()) == len(result)
