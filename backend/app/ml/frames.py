"""Convert between database rows and the pandas frames fraudml works on.

fraudml links the three systems into one wide row per TransactionID (columns suffixed _gl, _ma,
_fa). The transactions table stores exactly those columns, so a row can be turned back into
canonical records and re-linked when another system's record arrives later.
"""

import math
from collections.abc import Iterable, Mapping
from datetime import date

import numpy as np
import pandas as pd
from fraudml.canonical.normalise import empty_canonical, to_canonical
from fraudml.canonical.schema import ACCOUNT_KEY_FIELD, SYSTEMS
from fraudml.ingest.join_map import JOIN_MAP_COLUMNS

SYSTEM_FIELDS = [
    "account_key",
    "transaction_date",
    "amount",
    "currency",
    "country",
    "description",
    "rule_violations",
]
COALESCED_FIELDS = ["transaction_date", "amount", "currency", "country", "description"]
HISTORY_COLUMNS = [
    "account_key_gl",
    *[f"{field}_{s}" for field in ("transaction_date", "amount", "currency") for s in SYSTEMS],
    "period",
    "is_suspicious",
]


def py(value):
    """A plain Python value for the database: None for any missing value, date for timestamps."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        return [str(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def transaction_values(row: Mapping) -> dict:
    """Column values for the transactions table from one labelled row of the linked frame."""
    values: dict = {"transaction_id": str(row["transaction_id"])}
    for s in SYSTEMS:
        values[f"in_{s}"] = bool(row[f"in_{s}"])
        for field in SYSTEM_FIELDS:
            values[f"{field}_{s}"] = py(row.get(f"{field}_{s}"))
    values["expected_ma_key"] = py(row.get("expected_ma_key"))
    values["expected_fa_key"] = py(row.get("expected_fa_key"))
    values["gl_account_mapped"] = bool(row["gl_account_mapped"])
    values["gl_account_id"] = values["account_key_gl"]
    for field in COALESCED_FIELDS:
        values[field] = next(
            (values[f"{field}_{s}"] for s in SYSTEMS if values[f"{field}_{s}"] is not None), None
        )
    values["break_types"] = [str(b) for b in row["break_types"]]
    values["is_suspicious"] = bool(row["is_suspicious"])
    return values


def canonical_record(system: str, transaction_id: str, record: Mapping) -> pd.DataFrame:
    """One system's record as a one-row canonical frame, normalised like a file load.

    `record` has account_key, transaction_date, amount, currency, country and description.
    """
    when = record.get("transaction_date")
    amount = record.get("amount")
    raw = {
        "TransactionID": transaction_id,
        "TransactionDate": when.isoformat() if isinstance(when, date) else when,
        "Amount": None if amount is None else f"{float(amount):.2f}",
        "Currency": record.get("currency"),
        "Country": record.get("country"),
        "Description": record.get("description"),
        ACCOUNT_KEY_FIELD[system]: record.get("account_key"),
    }
    return to_canonical(pd.DataFrame([raw], dtype=str), system)


def stored_record(tx, system: str) -> dict | None:
    """A stored transaction's record for one system, or None if that system has none."""
    if not getattr(tx, f"in_{system}"):
        return None
    return {
        field: getattr(tx, f"{field}_{system}")
        for field in SYSTEM_FIELDS
        if field != "rule_violations"
    }


def canonical_frames(transaction_id: str, records: Mapping[str, Mapping | None]) -> dict:
    """Canonical frames for all three systems; a missing record gives an empty frame."""
    return {
        s: (
            canonical_record(s, transaction_id, records[s])
            if records.get(s) is not None
            else empty_canonical(s)
        )
        for s in SYSTEMS
    }


def join_map_frame(rows: Iterable[tuple]) -> pd.DataFrame:
    """Join map rows (in JOIN_MAP_COLUMNS order) as the frame fraudml's linker expects."""
    df = pd.DataFrame(list(rows), columns=JOIN_MAP_COLUMNS)
    for col in ("effective_from", "effective_to"):
        df[col] = pd.to_datetime(df[col])
    return df


def history_frame(rows: Iterable[tuple]) -> pd.DataFrame | None:
    """Earlier transactions (in HISTORY_COLUMNS order) for behavioural features; None if empty."""
    df = pd.DataFrame(list(rows), columns=HISTORY_COLUMNS)
    if df.empty:
        return None
    for s in SYSTEMS:
        df[f"transaction_date_{s}"] = pd.to_datetime(df[f"transaction_date_{s}"])
        df[f"amount_{s}"] = df[f"amount_{s}"].astype("float64")
    df["is_suspicious"] = df["is_suspicious"].astype(bool)
    return df
