import math

import pandas as pd
import pytest

from fraudml.scoring.explain import _raw_feature, top_factors
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
