"""Per-transaction explanations: feature contributions (log-odds) turned into plain reasons."""

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from fraudml.features.build import CATEGORICAL

SYSTEM_LABELS = {"gl": "GL", "ma": "MA", "fa": "FA"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FEATURE_LABELS = {
    "amount": "Transaction amount",
    "log_abs_amount": "Transaction size (log)",
    "is_round_amount": "Round amount",
    "day_of_month": "Day of month",
    "weekday": "Day of week",
    "is_month_end": "Month-end timing",
    "currency": "Currency",
    "country": "Country",
    "description": "Description",
}


def _raw_feature(transformed_name: str) -> str:
    """'num__max_amt_reldiff' -> 'max_amt_reldiff'; 'cat__currency_USD' -> 'currency'."""
    name = transformed_name.split("__", 1)[-1]
    if transformed_name.startswith("cat__"):
        for col in CATEGORICAL:
            if name.startswith(col + "_"):
                return col
    return name


def contributions(pipeline: Pipeline, X: pd.DataFrame) -> pd.DataFrame:
    """Contribution of each raw feature to each row's log-odds (positive = raises risk)."""
    prep, model = pipeline.named_steps["prep"], pipeline.named_steps["model"]
    Xt = prep.transform(X)
    names = prep.get_feature_names_out()
    if hasattr(model, "booster_"):  # LightGBM: exact TreeSHAP values
        contrib = model.predict(Xt, pred_contrib=True)[:, :-1]
    elif hasattr(model, "coef_"):  # linear: coefficient x standardised value
        contrib = np.asarray(Xt) * model.coef_[0]
    else:
        raise TypeError(f"No explanation method for {type(model).__name__}")
    frame = pd.DataFrame(contrib, columns=names, index=X.index)
    return frame.T.groupby(_raw_feature).sum().T


def _fmt_amount(v) -> str:
    return "missing" if pd.isna(v) else f"{v:,.2f}"


def _amounts(row: pd.Series) -> str:
    return ", ".join(
        f"{label} {_fmt_amount(row.get(f'amount_{s}'))}" for s, label in SYSTEM_LABELS.items()
    )


def _missing(row: pd.Series) -> str:
    missing = [label for s, label in SYSTEM_LABELS.items() if not row.get(f"in_{s}", True)]
    return f"Not found in {', '.join(missing)}." if missing else "Present in all three systems."


def _currencies(row: pd.Series) -> str:
    return ", ".join(
        f"{label} {row.get(f'currency_{s}') if pd.notna(row.get(f'currency_{s}')) else 'missing'}"
        for s, label in SYSTEM_LABELS.items()
    )


def _dates(row: pd.Series) -> str:
    parts = []
    for s, label in SYSTEM_LABELS.items():
        d = row.get(f"transaction_date_{s}")
        parts.append(f"{label} {'missing' if pd.isna(d) else pd.Timestamp(d).date()}")
    return ", ".join(parts)


def _rule_ids(row: pd.Series) -> str:
    ids = set()
    for s in SYSTEM_LABELS:
        values = row.get(f"rule_violations_{s}")
        if isinstance(values, (list, tuple, np.ndarray)):
            ids.update(str(v) for v in values)
    return ", ".join(sorted(ids)) or "unknown"


BREAK_REASONS = {
    "missing_in_gl": _missing,
    "missing_in_ma": _missing,
    "missing_in_fa": _missing,
    "amount_mismatch": lambda r: f"Amounts disagree across systems ({_amounts(r)}).",
    "date_mismatch": lambda r: f"Dates disagree across systems ({_dates(r)}).",
    "currency_mismatch": lambda r: f"Systems disagree on the currency ({_currencies(r)}).",
    "unmapped_account": lambda r: (
        f"Account {r.get('account_key_gl')} has no join-map entry for this date."
    ),
    "key_mismatch": lambda r: (
        f"MA or FA key does not match the join map for account {r.get('account_key_gl')}."
    ),
    "rule_violation": lambda r: f"Breaks business rule(s) {_rule_ids(r)} ({_amounts(r)}).",
}


def break_reason(break_type: str, row: pd.Series) -> str:
    return BREAK_REASONS.get(break_type, lambda r: break_type.replace("_", " ") + ".")(row)


def reason(feature: str, row: pd.Series) -> str | None:
    """One sentence for a feature using the transaction's own values; None if not describable."""
    if feature in ("in_gl", "in_ma", "in_fa", "n_systems"):
        return _missing(row)
    if feature.startswith("amt_reldiff") or feature in ("max_amt_reldiff", "max_amt_absdiff"):
        return BREAK_REASONS["amount_mismatch"](row)
    value = row.get(feature)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    templates = {
        "amount_sign_conflict": lambda: (
            f"Systems record the amount with opposite signs ({_amounts(row)})."
        ),
        "max_date_gap_days": lambda: f"Dates differ by {int(value)} days across systems.",
        "n_currencies": lambda: BREAK_REASONS["currency_mismatch"](row),
        "account_unmapped": lambda: BREAK_REASONS["unmapped_account"](row),
        "key_mismatch": lambda: BREAK_REASONS["key_mismatch"](row),
        "n_rule_violations": lambda: f"Breaks {int(value)} business rule check(s).",
        "amount_negative": lambda: f"An amount is negative ({_amounts(row)}).",
        "amount_over_limit": lambda: f"An amount is above the 100,000 limit ({_amounts(row)}).",
        "date_outside_period": lambda: "Transaction date falls outside the reporting month.",
        "acct_amount_zscore": lambda: (
            f"Amount is {value:.1f} standard deviations from this account's usual amount."
        ),
        "acct_amount_to_prior_max": lambda: (
            f"Amount is {value:.1f}x this account's previous largest."
        ),
        "acct_new_currency": lambda: f"First {row.get('currency')} transaction for this account.",
        "acct_prior_month_breaks": lambda: (
            f"Account had {int(value)} suspicious transaction(s) in earlier months."
        ),
        "acct_prior_txn_count": lambda: f"Account has {int(value)} earlier transactions.",
        "acct_days_since_last_txn": lambda: (
            f"{int(value)} days since the account's previous transaction."
        ),
        "acct_prior_mean_amount": lambda: f"Account's usual amount is {value:,.2f}.",
        "weekday": lambda: f"Day of week: {WEEKDAYS[int(value)]}.",
    }
    if feature in templates:
        return templates[feature]()
    label = FEATURE_LABELS.get(feature, feature.replace("_", " ").capitalize())
    shown = f"{value:,.2f}" if isinstance(value, float) else value
    return f"{label}: {shown}."


def top_factors(
    contrib: pd.Series, row: pd.Series, k: int = 5, min_contribution: float = 0.25
) -> list[dict]:
    """Up to k reasons pushing risk up, strongest first.

    Contributions are in log-odds; tiny ones are noise and are dropped. Features that produce
    the same sentence (e.g. several amount-difference features) are merged.
    """
    merged: dict[str, dict] = {}
    for feature, c in contrib[contrib >= min_contribution].sort_values(ascending=False).items():
        text = reason(feature, row)
        if text is None:
            continue
        entry = merged.setdefault(text, {"features": [], "contribution": 0.0, "reason": text})
        entry["features"].append(feature)
        entry["contribution"] += float(c)
    ranked = sorted(merged.values(), key=lambda e: e["contribution"], reverse=True)[:k]
    for e in ranked:
        e["contribution"] = round(e["contribution"], 4)
    return ranked
