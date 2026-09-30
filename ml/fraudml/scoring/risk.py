"""Turn a calibrated probability plus deterministic break checks into a 0-100 risk score."""

import math

# Minimum score when a deterministic check fires. A model score above the floor wins.
RULE_FLOORS = {
    "rule_violation": 90,
    "missing_in_gl": 80,
    "missing_in_ma": 80,
    "missing_in_fa": 80,
    "unmapped_account": 80,
    "key_mismatch": 80,
    "amount_mismatch": 70,
    "currency_mismatch": 70,
    "date_mismatch": 70,
}

BANDS = [(90, "critical"), (70, "high"), (40, "medium"), (0, "low")]


def band_for(score: int) -> str:
    for lower, name in BANDS:
        if score >= lower:
            return name
    return "low"


def risk_score(probability: float, break_types: list[str] | None = None) -> tuple[int, int, str]:
    """Return (risk_score, model_score, band).

    model_score = round(100 * calibrated probability); risk_score also respects rule floors.
    """
    if probability is None or math.isnan(probability):
        raise ValueError("probability must be a number")
    model_score = int(round(100 * min(max(probability, 0.0), 1.0)))
    floor = max((RULE_FLOORS.get(t, 0) for t in break_types or []), default=0)
    score = max(model_score, floor)
    return score, model_score, band_for(score)
