"""Join map reader: links GL account ids to MA customer keys and FA keys."""

from pathlib import Path

import pandas as pd

from fraudml.errors import IngestionError

JOIN_MAP_COLUMNS = [
    "gl_account_id",
    "ma_customer_key",
    "fa_key",
    "entity",
    "effective_from",
    "effective_to",
]


def read_join_map(path: str | Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise IngestionError(f"Cannot read join map {path}: {exc}") from exc

    missing = [c for c in JOIN_MAP_COLUMNS if c not in df.columns]
    if missing:
        raise IngestionError(f"Join map is missing columns: {missing}")

    df = df[JOIN_MAP_COLUMNS].copy()
    for col in ("effective_from", "effective_to"):
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    if df[["effective_from", "effective_to"]].isna().any().any():
        raise IngestionError("Join map has invalid effective dates")
    return df
