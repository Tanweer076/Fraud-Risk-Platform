"""Turn a raw source frame into the canonical schema."""

import pandas as pd

from fraudml.canonical.schema import (
    ACCOUNT_KEY_FIELD,
    CANONICAL_COLUMNS,
    SOURCE_TO_CANONICAL,
)
from fraudml.errors import IngestionError


def to_canonical(raw: pd.DataFrame, system: str) -> pd.DataFrame:
    """Rename, type and tidy a raw frame from one system.

    Amounts are parsed to float (MA sends them as strings); unparseable amounts become NaN.
    The raw date string is kept so invalid dates stay visible to the rule checks.
    """
    key_col = ACCOUNT_KEY_FIELD[system]
    required = [*SOURCE_TO_CANONICAL, key_col]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise IngestionError(f"{system.upper()} source is missing columns: {missing}")

    df = raw[required].rename(columns={**SOURCE_TO_CANONICAL, key_col: "account_key"}).copy()
    for col in ("transaction_id", "account_key", "transaction_date_raw", "currency", "country"):
        df[col] = df[col].astype("string").str.strip()
    df["description"] = df["description"].astype("string")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").round(2)
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date_raw"], format="%Y-%m-%d", errors="coerce"
    )
    df["source_system"] = system
    return df[CANONICAL_COLUMNS].reset_index(drop=True)


def empty_canonical(system: str) -> pd.DataFrame:
    """A canonical frame with no rows, for a system that has no record of a transaction."""
    df = pd.DataFrame({c: pd.Series(dtype="string") for c in CANONICAL_COLUMNS})
    df["amount"] = df["amount"].astype("float64")
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["source_system"] = pd.Series([], dtype=object)
    return df
