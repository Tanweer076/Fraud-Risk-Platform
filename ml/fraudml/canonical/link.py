"""Link the three systems' records into one wide row per TransactionID."""

import pandas as pd

from fraudml.canonical.schema import SYSTEMS

LINKED_FIELDS = ["account_key", "transaction_date", "amount", "currency", "country", "description"]


def link_systems(records: dict[str, pd.DataFrame], join_map: pd.DataFrame) -> pd.DataFrame:
    """Outer-join GL, MA and FA on transaction_id and resolve account keys via the join map.

    Output columns per system `s`: in_s, account_key_s, transaction_date_s, amount_s,
    currency_s, country_s, description_s, rule_violations_s (when present on the input).
    Plus `expected_ma_key` / `expected_fa_key`: the keys the join map gives for the GL account,
    using the mapping effective on the GL transaction date.
    """
    linked: pd.DataFrame | None = None
    for system in SYSTEMS:
        df = records[system]
        dupes = df["transaction_id"].duplicated(keep=False)
        if dupes.any():
            raise ValueError(
                f"{system.upper()} has {int(dupes.sum())} rows with duplicate TransactionID"
            )
        cols = [c for c in [*LINKED_FIELDS, "rule_violations"] if c in df.columns]
        wide = df.set_index("transaction_id")[cols].add_suffix(f"_{system}")
        wide[f"in_{system}"] = True
        linked = wide if linked is None else linked.join(wide, how="outer")

    linked = linked.reset_index()
    for system in SYSTEMS:
        linked[f"in_{system}"] = linked[f"in_{system}"].fillna(False).astype(bool)

    return _resolve_keys(linked, join_map)


def _resolve_keys(linked: pd.DataFrame, join_map: pd.DataFrame) -> pd.DataFrame:
    has_gl = linked["in_gl"]
    candidates = linked.loc[has_gl, ["transaction_id", "account_key_gl", "transaction_date_gl"]]
    merged = candidates.merge(
        join_map, left_on="account_key_gl", right_on="gl_account_id", how="inner"
    )
    # Undated GL rows still resolve; dated rows need a mapping effective on that date.
    effective = merged["transaction_date_gl"].isna() | (
        (merged["effective_from"] <= merged["transaction_date_gl"])
        & (merged["transaction_date_gl"] <= merged["effective_to"])
    )
    resolved = (
        merged[effective]
        .drop_duplicates("transaction_id")
        .set_index("transaction_id")[["ma_customer_key", "fa_key"]]
        .rename(columns={"ma_customer_key": "expected_ma_key", "fa_key": "expected_fa_key"})
    )
    linked = linked.join(resolved, on="transaction_id")
    linked["gl_account_mapped"] = linked["expected_ma_key"].notna()
    return linked
