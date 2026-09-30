"""EDA computations over the labelled monthly frames written by `fraudml label`.

Every function takes the concatenated labelled frame (with a `period` column) and returns a
small DataFrame or dict, so the report layer only formats and plots.
"""

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from fraudml.canonical.schema import SYSTEMS
from fraudml.labels.break_labeller import BREAK_TYPES

SEGMENTS = ["currency", "country", "description", "weekday", "amount_band", "month_part"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_labelled(processed_dir: str | Path) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(processed_dir).glob("labelled_*.parquet")):
        df = pd.read_parquet(path)
        df["period"] = re.search(r"(\d{6})", path.name).group(1)
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No labelled_*.parquet files in {processed_dir}")
    return add_views(pd.concat(frames, ignore_index=True))


def _coalesce(df: pd.DataFrame, field: str) -> pd.Series:
    """Value from GL, else MA, else FA (a transaction can be missing from any one system)."""
    out = df[f"{field}_gl"]
    for system in SYSTEMS[1:]:
        out = out.fillna(df[f"{field}_{system}"])
    return out


def add_views(df: pd.DataFrame) -> pd.DataFrame:
    """Add single-value segment columns used across the report."""
    df = df.copy()
    for field in ("currency", "country", "description", "transaction_date", "amount"):
        df[field] = _coalesce(df, field)
    df["account"] = df["account_key_gl"]
    df["weekday"] = pd.Categorical(
        df["transaction_date"].dt.dayofweek.map(dict(enumerate(WEEKDAYS))),
        categories=WEEKDAYS,
        ordered=True,
    )
    bands = [-np.inf, 0, 20_000, 40_000, 60_000, 80_000, 100_000, np.inf]
    labels = ["<0", "0-20k", "20-40k", "40-60k", "60-80k", "80-100k", ">100k"]
    df["amount_band"] = pd.cut(df["amount"], bands, labels=labels, right=False)
    day = df["transaction_date"].dt.day
    df["month_part"] = pd.cut(day, [0, 10, 20, 31], labels=["days 1-10", "11-20", "21-31"])
    return df


def overview(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("period")
    out = pd.DataFrame(
        {
            "transactions": g.size(),
            "in_gl": g["in_gl"].sum(),
            "in_ma": g["in_ma"].sum(),
            "in_fa": g["in_fa"].sum(),
            "suspicious": g["is_suspicious"].sum(),
        }
    )
    out["suspicious_rate"] = out["suspicious"] / out["transactions"]
    return out


def presence_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Transactions per period by which systems contain them (e.g. 'GL+MA', FA missing)."""
    label = df[[f"in_{s}" for s in SYSTEMS]].apply(
        lambda r: "+".join(s.upper() for s in SYSTEMS if r[f"in_{s}"]), axis=1
    )
    return pd.crosstab(label.rename("present_in"), df["period"])


def break_type_counts(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("period")[[f"brk_{t}" for t in BREAK_TYPES]]
        .sum()
        .T.rename(index=lambda c: c.removeprefix("brk_"))
    )


def break_multiplicity(df: pd.DataFrame) -> pd.DataFrame:
    """How many break types each suspicious transaction has."""
    s = df[df["is_suspicious"]]
    return pd.crosstab(s["n_break_types"].rename("break_types_per_txn"), s["period"])


def co_occurrence(df: pd.DataFrame) -> pd.DataFrame:
    """Count of suspicious transactions carrying each pair of break types."""
    flags = df.loc[df["is_suspicious"], [f"brk_{t}" for t in BREAK_TYPES]].astype(int)
    flags.columns = BREAK_TYPES
    return flags.T @ flags


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def segment_rates(df: pd.DataFrame, segment: str) -> pd.DataFrame:
    """Suspicious rate per segment value with a 95% Wilson interval."""
    g = df.groupby(segment, observed=True)["is_suspicious"].agg(["sum", "count"])
    g = g.rename(columns={"sum": "suspicious", "count": "transactions"})
    g["rate"] = g["suspicious"] / g["transactions"]
    ci = [
        wilson_interval(int(k), int(n))
        for k, n in zip(g["suspicious"], g["transactions"], strict=True)
    ]
    g["ci_low"], g["ci_high"] = zip(*ci, strict=True) if ci else ([], [])
    return g


def segment_spread(df: pd.DataFrame) -> pd.DataFrame:
    """For each segment: range of rates and whether any value's interval excludes the overall rate.

    A segment 'separates' when some value's 95% interval does not contain the overall rate.
    With many small values some separation happens by chance, so treat it as a lead, not proof.
    """
    overall = df["is_suspicious"].mean()
    rows = []
    for seg in SEGMENTS:
        r = segment_rates(df, seg)
        r = r[r["transactions"] >= 30]
        outside = ((r["ci_low"] > overall) | (r["ci_high"] < overall)).sum()
        rows.append(
            {
                "segment": seg,
                "values": len(r),
                "min_rate": r["rate"].min(),
                "max_rate": r["rate"].max(),
                "values_outside_ci": int(outside),
            }
        )
    return pd.DataFrame(rows).set_index("segment")


def amount_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Largest pairwise relative amount difference for amount-mismatch transactions."""
    s = df[df["brk_amount_mismatch"]]
    rel = pd.Series(0.0, index=s.index)
    for a, b in (("gl", "ma"), ("gl", "fa"), ("ma", "fa")):
        base = s[[f"amount_{a}", f"amount_{b}"]].abs().max(axis=1).replace(0, np.nan)
        d = (s[f"amount_{a}"] - s[f"amount_{b}"]).abs() / base
        rel = np.fmax(rel, d.fillna(0))
    return pd.DataFrame({"period": s["period"], "max_rel_delta": rel})


def date_deltas(df: pd.DataFrame) -> pd.Series:
    """Largest pairwise gap in days for date-mismatch transactions."""
    s = df[df["brk_date_mismatch"]]
    dates = s[[f"transaction_date_{x}" for x in SYSTEMS]]
    return (dates.max(axis=1) - dates.min(axis=1)).dt.days.rename("max_gap_days")


def account_history_effect(df: pd.DataFrame) -> pd.DataFrame:
    """Suspicious rate in each month for accounts that did / did not break the month before.

    Months that follow a month with no suspicious transactions are skipped.
    """
    periods = sorted(df["period"].unique())
    rows = []
    for prev, cur in zip(periods, periods[1:], strict=False):
        broke = set(df.loc[(df["period"] == prev) & df["is_suspicious"], "account"].dropna())
        if not broke:
            continue  # nothing to compare against (e.g. after a clean month)
        cur_df = df[(df["period"] == cur) & df["account"].notna()]
        flag = cur_df["account"].isin(broke)
        for label, part in (("broke last month", cur_df[flag]), ("did not", cur_df[~flag])):
            rows.append(
                {
                    "period": cur,
                    "account_group": label,
                    "transactions": len(part),
                    "rate": part["is_suspicious"].mean() if len(part) else math.nan,
                }
            )
    return pd.DataFrame(rows, columns=["period", "account_group", "transactions", "rate"])


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """Population stability index of `actual` against quantile bins of `expected`."""
    expected, actual = expected.dropna(), actual.dropna()
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def drift(df: pd.DataFrame) -> pd.DataFrame:
    """PSI of each system's amount distribution against the first (baseline) month."""
    periods = sorted(df["period"].unique())
    base = df[df["period"] == periods[0]]
    rows = []
    for period in periods[1:]:
        cur = df[df["period"] == period]
        row = {"period": period}
        for s in SYSTEMS:
            row[f"amount_{s}_psi"] = psi(base[f"amount_{s}"], cur[f"amount_{s}"])
        rows.append(row)
    return pd.DataFrame(rows).set_index("period")
