"""Financial Accounting reader: CSV report."""

from pathlib import Path

import pandas as pd

from fraudml.canonical.normalise import to_canonical
from fraudml.errors import IngestionError


def read_fa_csv(path: str | Path) -> pd.DataFrame:
    try:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise IngestionError(f"Cannot read FA CSV {path}: {exc}") from exc
    return to_canonical(raw, "fa")
