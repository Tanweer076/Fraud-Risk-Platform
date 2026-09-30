import math

import pandas as pd
import pytest

from fraudml.models.evaluation import _thin, score_histogram
from fraudml.scoring.explain import _raw_feature, top_factors
from fraudml.scoring.materiality import exposure, priority, to_usd
from fraudml.scoring.risk import band_for, risk_score


@pytest.mark.parametrize(
    ("score", "band"), [(0, "low"), (39, "low"), (40, "medium"), (70, "high"), (90, "critical")]
)
def test_bands(score, band):
    assert band_for(score) == band


def test_score_is_scaled_probability_without_breaks():
    assert risk_score(0.123) == (12, 12, "low")
    assert risk_score(0.95) == (95, 95, "critical")


def test_rule_floor_lifts_low_model_score():
    assert risk_score(0.05, ["unmapped_account"]) == (80, 5, "high")
    assert risk_score(0.05, ["amount_mismatch", "rule_violation"]) == (90, 5, "critical")


def test_model_score_above_floor_wins():
    assert risk_score(0.99, ["date_mismatch"]) == (99, 99, "critical")


def test_invalid_probability_raises():
    with pytest.raises(ValueError):
        risk_score(math.nan)


def test_raw_feature_names():
    assert _raw_feature("num__max_amt_reldiff") == "max_amt_reldiff"
    assert _raw_feature("cat__currency_USD") == "currency"
    assert _raw_feature("cat__description_Vendor payment") == "description"


def test_top_factors_merge_same_reason_and_drop_noise():
    row = pd.Series(
        {
            "amount_gl": 100.0,
            "amount_ma": 300.0,
            "amount_fa": 100.0,
            "in_gl": True,
            "in_ma": True,
            "in_fa": True,
            "country": "US",
        }
    )
    contrib = pd.Series(
        {"max_amt_reldiff": 3.0, "amt_reldiff_gl_ma": 2.0, "country": 0.1, "in_fa": -1.0}
    )
    factors = top_factors(contrib, row)
    assert len(factors) == 1
    assert factors[0]["contribution"] == pytest.approx(5.0)
    assert factors[0]["features"] == ["max_amt_reldiff", "amt_reldiff_gl_ma"]
    assert "GL 100.00, MA 300.00, FA 100.00" in factors[0]["reason"]


def test_exposure_is_the_difference_for_amount_mismatch_else_the_amount():
    assert exposure(5000.0, 12.5, ["amount_mismatch"]) == 12.5
    assert exposure(5000.0, 0.0, ["missing_in_fa"]) == 5000.0
    assert exposure(-5000.0, 12.5, ["amount_mismatch", "rule_violation"]) == 5000.0
    assert exposure(5000.0, 0.0, []) == 0.0
    assert exposure(float("nan"), float("nan"), ["missing_in_gl"]) == 0.0


def test_to_usd_uses_rates_and_takes_unknown_currencies_at_par():
    assert to_usd(100.0, "EUR") == pytest.approx(108.0)
    assert to_usd(100.0, "jpy") == pytest.approx(0.67)
    assert to_usd(100.0, "XYZ") == 100.0
    assert to_usd(100.0, None) == 100.0


def test_priority_ranks_large_breaks_above_small_ones():
    assert priority(90, 0.0) == 45
    assert priority(90, 1_000_000.0) == 90
    assert priority(90, 5_000_000.0) == 90
    assert priority(90, 50.0) < priority(90, 50_000.0) < priority(90, 500_000.0)
    assert priority(0, 1_000_000.0) == 0


def test_thin_keeps_both_ends_and_caps_points():
    (thinned,) = _thin(list(range(1000)), max_points=10)
    assert len(thinned) == 10 and thinned[0] == 0 and thinned[-1] == 999
    (small,) = _thin([1, 2, 3], max_points=10)
    assert list(small) == [1, 2, 3]


def test_score_histogram_puts_100_in_the_last_bin():
    bins = score_histogram([0, 9, 10, 95, 100])
    assert [b["count"] for b in bins] == [2, 1, 0, 0, 0, 0, 0, 0, 0, 2]
    assert bins[-1] == {"score_from": 90, "score_to": 100, "count": 2}
    assert bins[0]["score_to"] == 9
