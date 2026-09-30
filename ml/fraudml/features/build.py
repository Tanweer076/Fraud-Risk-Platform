"""Feature engineering shared by training and serving.

Input is the linked wide frame (one row per TransactionID, columns suffixed _gl/_ma/_fa, as
written by `fraudml label`). Behavioural features look only at the same account's
transactions on earlier days, so they are safe to compute for both history and new rows.

Feature groups:
  cross_system - presence in each system and how far the systems' values disagree
  rules        - business-rule and range checks
  behavioural  - the account's own history (earlier days / earlier months only)
  attributes   - the transaction's own fields
"""

from itertools import combinations

import numpy as np
import pandas as pd

from fraudml.canonical.schema import SYSTEMS

AMOUNT_LIMIT = 100_000
PAIRS = list(combinations(SYSTEMS, 2))

CROSS_SYSTEM = [
    "in_gl",
    "in_ma",
    "in_fa",
    "n_systems",
    *[f"amt_reldiff_{a}_{b}" for a, b in PAIRS],
    "max_amt_reldiff",
    "max_amt_absdiff",
    "amount_sign_conflict",
    "max_date_gap_days",
    "n_currencies",
    "account_unmapped",
    "key_mismatch",
]
RULES = ["n_rule_violations", "amount_negative", "amount_over_limit", "date_outside_period"]
BEHAVIOURAL = [
    "acct_prior_txn_count",
    "acct_prior_mean_amount",
    "acct_amount_zscore",
    "acct_amount_to_prior_max",
    "acct_days_since_last_txn",
    "acct_new_currency",
    "acct_prior_month_breaks",
]
ATTRIBUTE_NUMERIC = [
    "amount",
    "log_abs_amount",
    "is_round_amount",
    "day_of_month",
    "weekday",
    "is_month_end",
]
CATEGORICAL = ["currency", "country", "description"]

GROUPS = {
    "cross_system": CROSS_SYSTEM,
    "rules": RULES,
    "behavioural": BEHAVIOURAL,
    "attributes": ATTRIBUTE_NUMERIC + CATEGORICAL,
}
ALL_FEATURES = CROSS_SYSTEM + RULES + BEHAVIOURAL + ATTRIBUTE_NUMERIC + CATEGORICAL
NUMERIC_FEATURES = [f for f in ALL_FEATURES if f not in CATEGORICAL]


def coalesce(df: pd.DataFrame, field: str) -> pd.Series:
    """Value from GL, else MA, else FA."""
    out = df[f"{field}_gl"]
    for system in SYSTEMS[1:]:
        out = out.fillna(df[f"{field}_{system}"])
    return out


def _cross_system(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    for s in SYSTEMS:
        f[f"in_{s}"] = df[f"in_{s}"].astype(int)
    f["n_systems"] = f[[f"in_{s}" for s in SYSTEMS]].sum(axis=1)

    rel_cols, abs_cols = [], []
    sign_conflict = pd.Series(False, index=df.index)
    for a, b in PAIRS:
        x, y = df[f"amount_{a}"], df[f"amount_{b}"]
        diff = (x - y).abs()
        scale = pd.concat([x.abs(), y.abs()], axis=1).max(axis=1).replace(0, np.nan)
        f[f"amt_reldiff_{a}_{b}"] = (diff / scale).fillna(0.0)
        abs_cols.append(diff.fillna(0.0))
        rel_cols.append(f"amt_reldiff_{a}_{b}")
        sign_conflict |= (np.sign(x) * np.sign(y) < 0).fillna(False)
    f["max_amt_reldiff"] = f[rel_cols].max(axis=1)
    f["max_amt_absdiff"] = pd.concat(abs_cols, axis=1).max(axis=1)
    f["amount_sign_conflict"] = sign_conflict.astype(int)

    dates = df[[f"transaction_date_{s}" for s in SYSTEMS]]
    f["max_date_gap_days"] = (dates.max(axis=1) - dates.min(axis=1)).dt.days.fillna(0)
    f["n_currencies"] = df[[f"currency_{s}" for s in SYSTEMS]].nunique(axis=1)

    f["account_unmapped"] = (df["in_gl"] & ~df["gl_account_mapped"]).astype(int)
    key_mismatch = pd.Series(False, index=df.index)
    for s, expected in (("ma", "expected_ma_key"), ("fa", "expected_fa_key")):
        both = df[expected].notna() & df[f"account_key_{s}"].notna()
        key_mismatch |= both & (df[expected] != df[f"account_key_{s}"]).fillna(False)
    f["key_mismatch"] = key_mismatch.astype(int)
    return f


def _rules(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    lists = [df[c] for c in (f"rule_violations_{s}" for s in SYSTEMS) if c in df.columns]

    def _count(values) -> int:
        return len(values) if isinstance(values, (list, np.ndarray)) else 0

    def _has_period(values) -> bool:
        return isinstance(values, (list, np.ndarray)) and "PERIOD" in list(values)

    f["n_rule_violations"] = sum((col.map(_count) for col in lists), start=0)
    f["date_outside_period"] = (
        pd.concat([col.map(_has_period) for col in lists], axis=1).any(axis=1).astype(int)
        if lists
        else 0
    )
    amounts = df[[f"amount_{s}" for s in SYSTEMS]]
    f["amount_negative"] = (amounts < 0).any(axis=1).astype(int)
    f["amount_over_limit"] = (amounts > AMOUNT_LIMIT).any(axis=1).astype(int)
    return f


def _attributes(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    amount = coalesce(df, "amount")
    date = coalesce(df, "transaction_date")
    f["amount"] = amount
    f["log_abs_amount"] = np.log1p(amount.abs())
    f["is_round_amount"] = ((amount % 100).abs() < 0.005).astype(int)
    f["day_of_month"] = date.dt.day
    f["weekday"] = date.dt.dayofweek
    f["is_month_end"] = (date.dt.day >= 28).astype(int)
    for col in CATEGORICAL:
        f[col] = coalesce(df, col).astype(object)
    return f


def _behavioural(df: pd.DataFrame, history: pd.DataFrame | None) -> pd.DataFrame:
    """Per-account history features using only earlier days (and earlier months for breaks).

    `history` holds already-known transactions (with `is_suspicious` when known) and must not
    contain the rows being scored. When it is None, `df` serves as its own history, which is
    how training builds the features.
    """
    cols = ["account", "date", "amount", "currency", "period", "is_suspicious"]

    def _frame(src: pd.DataFrame, is_target: bool) -> pd.DataFrame:
        out = pd.DataFrame(
            {
                "account": src["account_key_gl"],
                "date": coalesce(src, "transaction_date"),
                "amount": coalesce(src, "amount"),
                "currency": coalesce(src, "currency"),
                "period": src["period"] if "period" in src else pd.NA,
                "is_suspicious": src["is_suspicious"] if "is_suspicious" in src else np.nan,
            },
            index=src.index,
        )[cols]
        out["is_target"] = is_target
        out["row"] = np.arange(len(src)) if is_target else -1
        return out

    frames = [_frame(df, True)]
    if history is not None:
        frames.append(_frame(history, False))
    both = pd.concat(frames, ignore_index=True)
    both = both[both["account"].notna() & both["date"].notna()]
    both["amount_sq"] = both["amount"] ** 2

    daily = (
        both.groupby(["account", "date"])
        .agg(
            n=("amount", "size"), s=("amount", "sum"), ss=("amount_sq", "sum"), mx=("amount", "max")
        )
        .reset_index()
        .sort_values(["account", "date"])
    )
    g = daily.groupby("account")
    daily["prior_n"] = g["n"].cumsum() - daily["n"]
    daily["prior_s"] = g["s"].cumsum() - daily["s"]
    daily["prior_ss"] = g["ss"].cumsum() - daily["ss"]
    daily["prior_max"] = g["mx"].cummax().groupby(daily["account"]).shift(1)
    daily["prev_date"] = g["date"].shift(1)

    first_ccy = both.groupby(["account", "currency"])["date"].min().rename("first_ccy_date")

    monthly = (
        both.dropna(subset=["period"])
        .groupby(["account", "period"])["is_suspicious"]
        .sum(min_count=1)
        .fillna(0)
        .reset_index()
        .sort_values(["account", "period"])
    )
    monthly["prior_month_breaks"] = (
        monthly.groupby("account")["is_suspicious"].cumsum() - monthly["is_suspicious"]
    )

    t = both[both["is_target"]].merge(daily, on=["account", "date"], how="left")
    t = t.merge(first_ccy, left_on=["account", "currency"], right_index=True, how="left")
    t = t.merge(
        monthly[["account", "period", "prior_month_breaks"]], on=["account", "period"], how="left"
    )

    mean = t["prior_s"] / t["prior_n"].replace(0, np.nan)
    var = t["prior_ss"] / t["prior_n"].replace(0, np.nan) - mean**2
    std = np.sqrt(var.clip(lower=0))
    f = pd.DataFrame(
        {
            "acct_prior_txn_count": t["prior_n"],
            "acct_prior_mean_amount": mean,
            "acct_amount_zscore": ((t["amount"] - mean) / std.replace(0, np.nan)).clip(-50, 50),
            "acct_amount_to_prior_max": t["amount"] / t["prior_max"].replace(0, np.nan),
            "acct_days_since_last_txn": (t["date"] - t["prev_date"]).dt.days,
            "acct_new_currency": (t["first_ccy_date"] >= t["date"]).astype(int),
            "acct_prior_month_breaks": t["prior_month_breaks"],
        }
    )
    f.index = t["row"].to_numpy()
    out = f.reindex(range(len(df)))
    out.index = df.index
    out["acct_prior_txn_count"] = out["acct_prior_txn_count"].fillna(0)
    out["acct_prior_month_breaks"] = out["acct_prior_month_breaks"].fillna(0)
    out["acct_new_currency"] = out["acct_new_currency"].fillna(1)
    return out


def build_features(df: pd.DataFrame, history: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return one row of features per row of `df`, columns in ALL_FEATURES order."""
    parts = [_cross_system(df), _rules(df), _behavioural(df, history), _attributes(df)]
    return pd.concat(parts, axis=1)[ALL_FEATURES]
