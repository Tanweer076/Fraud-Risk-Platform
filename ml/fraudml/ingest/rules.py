"""Business rules: parse `business_rules.txt` and check canonical records against it.

File format, one rule per line: `ID|Field|TYPE|PARAM|Message`. Row-level types are REGEX, DATE,
RANGE and LOOKUP. Other types (INGEST, DEFINE, SUM) describe the engine, not rows, and are
kept for reference only. A rule whose field does not exist in the canonical schema is skipped.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fraudml.errors import IngestionError

ROW_RULE_TYPES = {"REGEX", "DATE", "RANGE", "LOOKUP"}

# Rule-file field name -> (canonical column, systems it applies to).
FIELD_MAP = {
    "TransactionID": ("transaction_id", {"gl", "ma", "fa"}),
    "AccountID": ("account_key", {"gl"}),  # ACC#### format is the GL key only
    "TransactionDate": ("transaction_date_raw", {"gl", "ma", "fa"}),
    "Amount": ("amount", {"gl", "ma", "fa"}),
    "Currency": ("currency", {"gl", "ma", "fa"}),
    "Country": ("country", {"gl", "ma", "fa"}),
    "Description": ("description", {"gl", "ma", "fa"}),
}

PERIOD_RULE_ID = "PERIOD"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    field: str
    rule_type: str
    param: str
    message: str


def parse_rules(path: str | Path) -> list[Rule]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise IngestionError(f"Cannot read business rules {path}: {exc}") from exc

    rules = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise IngestionError(f"Business rule line {lineno} has {len(parts)} fields, want 5")
        rules.append(Rule(*(p.strip() for p in parts)))
    return rules


def _violates(rule: Rule, values: pd.Series) -> pd.Series:
    """True where a value breaks the rule. Missing values always break it."""
    missing = values.isna()
    if rule.rule_type == "REGEX":
        ok = values.astype("string").str.fullmatch(rule.param.rstrip("$") + "$", na=False)
    elif rule.rule_type == "DATE":
        ok = pd.to_datetime(values, format=rule.param, errors="coerce").notna()
    elif rule.rule_type == "RANGE":
        low, high = (float(x) for x in rule.param.split(","))
        num = pd.to_numeric(values, errors="coerce")
        ok = num.between(low, high)
    elif rule.rule_type == "LOOKUP":
        ok = values.isin(rule.param.split(","))
    else:
        raise ValueError(f"Not a row rule: {rule.rule_type}")
    return missing | ~ok.fillna(False).astype(bool)


def validate(records: pd.DataFrame, rules: list[Rule], period: str | None = None) -> pd.Series:
    """Return, per canonical record, the sorted list of violated rule ids.

    With `period` (YYYYMM), dates outside that month add a `PERIOD` violation.
    """
    violations: list[list[str]] = [[] for _ in range(len(records))]
    systems = records["source_system"]
    for rule in rules:
        if rule.rule_type not in ROW_RULE_TYPES or rule.field not in FIELD_MAP:
            continue
        column, applies_to = FIELD_MAP[rule.field]
        mask = systems.isin(applies_to) & _violates(rule, records[column])
        for i in mask[mask].index:
            violations[records.index.get_loc(i)].append(rule.rule_id)

    if period:
        month = records["transaction_date"].dt.strftime("%Y%m")
        outside = records["transaction_date"].notna() & (month != period)
        for i in outside[outside].index:
            violations[records.index.get_loc(i)].append(PERIOD_RULE_ID)

    return pd.Series([sorted(v) for v in violations], index=records.index, name="rule_violations")
