"""Derive the `is_suspicious` target from cross-system breaks.

A transaction is suspicious when any of these break types applies:
  missing_in_gl / missing_in_ma / missing_in_fa  - absent from a system
  amount_mismatch    - amounts differ by more than a cent between any two systems
  date_mismatch      - transaction dates differ between systems
  currency_mismatch  - currencies differ between systems
  unmapped_account   - GL account has no join-map entry effective on the transaction date
  key_mismatch       - MA/FA key differs from the one the join map gives for the GL account
  rule_violation     - any system's record breaks a business rule (incl. out-of-period date)
"""

from itertools import combinations

import pandas as pd

from fraudml.canonical.schema import SYSTEMS

AMOUNT_TOLERANCE = 0.005

BREAK_TYPES = [
    "missing_in_gl",
    "missing_in_ma",
    "missing_in_fa",
    "amount_mismatch",
    "date_mismatch",
    "currency_mismatch",
    "unmapped_account",
    "key_mismatch",
    "rule_violation",
]


def _pairwise_differs(linked: pd.DataFrame, field: str, numeric: bool = False) -> pd.Series:
    """True where two systems both have a value for `field` and the values differ."""
    out = pd.Series(False, index=linked.index)
    for a, b in combinations(SYSTEMS, 2):
        left, right = linked[f"{field}_{a}"], linked[f"{field}_{b}"]
        both = left.notna() & right.notna()
        if numeric:
            differs = (left - right).abs() > AMOUNT_TOLERANCE
        else:
            differs = left != right
        out |= both & differs.fillna(False).astype(bool)
    return out


def label_breaks(linked: pd.DataFrame) -> pd.DataFrame:
    df = linked.copy()
    flags = pd.DataFrame(index=df.index)
    for system in SYSTEMS:
        flags[f"missing_in_{system}"] = ~df[f"in_{system}"]
    flags["amount_mismatch"] = _pairwise_differs(df, "amount", numeric=True)
    flags["date_mismatch"] = _pairwise_differs(df, "transaction_date")
    flags["currency_mismatch"] = _pairwise_differs(df, "currency")
    flags["unmapped_account"] = df["in_gl"] & ~df["gl_account_mapped"]
    flags["key_mismatch"] = (
        df["expected_ma_key"].notna()
        & df["account_key_ma"].notna()
        & (df["expected_ma_key"] != df["account_key_ma"])
    ) | (
        df["expected_fa_key"].notna()
        & df["account_key_fa"].notna()
        & (df["expected_fa_key"] != df["account_key_fa"])
    )
    flags = flags.fillna(False).astype(bool)

    rule_cols = [f"rule_violations_{s}" for s in SYSTEMS if f"rule_violations_{s}" in df.columns]
    if rule_cols:
        flags["rule_violation"] = (
            df[rule_cols]
            .apply(lambda row: any(isinstance(v, list) and v for v in row), axis=1)
            .astype(bool)
        )
    else:
        flags["rule_violation"] = False

    for name in BREAK_TYPES:
        df[f"brk_{name}"] = flags[name]
    df["break_types"] = [
        [name for name in BREAK_TYPES if row[name]] for row in flags[BREAK_TYPES].to_dict("records")
    ]
    df["n_break_types"] = flags[BREAK_TYPES].sum(axis=1)
    df["is_suspicious"] = df["n_break_types"] > 0
    return df


def summarise(labelled: pd.DataFrame) -> dict:
    n = len(labelled)
    suspicious = int(labelled["is_suspicious"].sum())
    return {
        "transactions": n,
        "suspicious": suspicious,
        "suspicious_rate": round(suspicious / n, 4) if n else 0.0,
        "by_break_type": {t: int(labelled[f"brk_{t}"].sum()) for t in BREAK_TYPES},
    }
