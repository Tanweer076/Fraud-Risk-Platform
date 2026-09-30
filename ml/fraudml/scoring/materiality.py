"""Money at stake, so that large breaks rank above small ones.

Risk scores are close to all-or-nothing: a transaction with a break scores 70-100 whatever its
size. Priority scales the risk score by the break's exposure in USD, so a 50,000 mismatch comes
before a 0.50 one with the same risk score.
"""

import math

# Approximate rates, used only to rank work across currencies. Not for accounting.
FX_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "INR": 0.012,
    "JPY": 0.0067,
    "CAD": 0.73,
    "CHF": 1.12,
    "AUD": 0.66,
}
FULL_WEIGHT_EXPOSURE_USD = 1_000_000
MIN_WEIGHT = 0.5


def _number(value) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def exposure(amount, max_amt_absdiff, break_types: list[str] | None) -> float:
    """Amount at stake, in the transaction's own currency.

    An amount mismatch puts the difference at stake. Any other break (a missing record, an
    unmapped account, a rule breach) puts the whole amount at stake. No break, nothing at stake.
    """
    if not break_types:
        return 0.0
    at_stake = abs(_number(max_amt_absdiff) or 0.0)
    if any(t != "amount_mismatch" for t in break_types):
        at_stake = max(at_stake, abs(_number(amount) or 0.0))
    return at_stake


def to_usd(value: float, currency) -> float:
    """Convert with FX_TO_USD; an unknown currency is taken at par."""
    rate = FX_TO_USD.get(str(currency).upper(), 1.0) if isinstance(currency, str) else 1.0
    return value * rate


def priority(risk_score: int, exposure_usd: float) -> int:
    """Risk score weighted by exposure: half weight at 0 USD, full weight at 1,000,000 USD."""
    size = math.log10(1 + max(exposure_usd, 0.0)) / math.log10(FULL_WEIGHT_EXPOSURE_USD)
    weight = MIN_WEIGHT + (1 - MIN_WEIGHT) * min(1.0, size)
    return int(round(risk_score * weight))
