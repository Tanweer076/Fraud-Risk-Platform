import json

import pandas as pd

from fraudml.labels.break_labeller import summarise
from fraudml.pipeline import label_month, main

from .conftest import BASE, JOIN_MAP, write_month


def _label(tmp_path, rules_path, **kwargs):
    _, labelled = label_month(write_month(tmp_path, **kwargs), rules_path)
    return labelled.set_index("transaction_id")


def _with(row_index: int, **changes):
    rows = [list(r) for r in BASE]
    fields = ["id", "acc", "date", "amount", "ccy", "country", "desc"]
    for key, value in changes.items():
        rows[row_index][fields.index(key)] = value
    return [tuple(r) for r in rows]


def test_matching_systems_produce_no_breaks(tmp_path, rules_path):
    labelled = _label(tmp_path, rules_path)
    assert not labelled["is_suspicious"].any()
    assert labelled["break_types"].map(len).sum() == 0


def test_missing_record_is_flagged(tmp_path, rules_path):
    labelled = _label(tmp_path, rules_path, fa_rows=BASE[:2])
    row = labelled.loc["AAAAAAAAAAAAAAA3"]
    assert row["is_suspicious"]
    assert list(row["break_types"]) == ["missing_in_fa"]
    assert labelled["is_suspicious"].sum() == 1


def test_amount_mismatch_is_flagged_but_rounding_noise_is_not(tmp_path, rules_path):
    ma = _with(0, amount="100.001")  # rounds to 100.00, same as GL
    fa = _with(1, amount="260.50")
    labelled = _label(tmp_path, rules_path, ma_rows=ma, fa_rows=fa)
    assert not labelled.loc["AAAAAAAAAAAAAAA1", "is_suspicious"]
    assert list(labelled.loc["AAAAAAAAAAAAAAA2", "break_types"]) == ["amount_mismatch"]


def test_date_and_currency_mismatch_are_flagged(tmp_path, rules_path):
    ma = _with(0, date="2026-07-20")
    fa = _with(2, ccy="USD")
    labelled = _label(tmp_path, rules_path, ma_rows=ma, fa_rows=fa)
    assert list(labelled.loc["AAAAAAAAAAAAAAA1", "break_types"]) == ["date_mismatch"]
    assert list(labelled.loc["AAAAAAAAAAAAAAA3", "break_types"]) == ["currency_mismatch"]


def test_unmapped_account_is_flagged(tmp_path, rules_path):
    labelled = _label(tmp_path, rules_path, join_map=JOIN_MAP[:2])
    assert list(labelled.loc["AAAAAAAAAAAAAAA3", "break_types"]) == ["unmapped_account"]


def test_key_mismatch_is_flagged(tmp_path, rules_path):
    swapped = [JOIN_MAP[0], ("ACC0002", "CUS-000099", "FA-000002"), JOIN_MAP[2]]
    labelled = _label(tmp_path, rules_path, join_map=swapped)
    assert list(labelled.loc["AAAAAAAAAAAAAAA2", "break_types"]) == ["key_mismatch"]


def test_rule_violation_in_one_system_is_flagged(tmp_path, rules_path):
    rows = _with(0, amount="150000.00")
    labelled = _label(tmp_path, rules_path, gl_rows=rows, ma_rows=rows, fa_rows=rows)
    assert list(labelled.loc["AAAAAAAAAAAAAAA1", "break_types"]) == ["rule_violation"]


def test_summary_counts(tmp_path, rules_path):
    _, labelled = label_month(write_month(tmp_path, fa_rows=BASE[:2]), rules_path)
    summary = summarise(labelled)
    assert summary["transactions"] == 3
    assert summary["suspicious"] == 1
    assert summary["by_break_type"]["missing_in_fa"] == 1


def test_cli_writes_parquet_and_summary(tmp_path, rules_path, capsys):
    month = write_month(tmp_path / "raw", fa_rows=BASE[:2])
    out = tmp_path / "processed"
    code = main(["label", "--month-dir", str(month), "--rules", str(rules_path), "--out", str(out)])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["202607"]["suspicious"] == 1
    written = pd.read_parquet(out / "labelled_202607.parquet")
    assert written["is_suspicious"].sum() == 1


def test_cli_returns_error_code_for_missing_files(tmp_path, rules_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    code = main(["label", "--month-dir", str(empty), "--rules", str(rules_path)])
    assert code == 1


def test_rule_violations_survive_parquet_round_trip(tmp_path, rules_path):
    from fraudml.labels.break_labeller import label_breaks

    rows = _with(0, amount="150000.00")
    _, labelled = label_month(
        write_month(tmp_path, gl_rows=rows, ma_rows=rows, fa_rows=rows), rules_path
    )
    labelled.to_parquet(tmp_path / "l.parquet", index=False)
    reloaded = pd.read_parquet(tmp_path / "l.parquet")  # lists come back as numpy arrays
    relabelled = label_breaks(reloaded).set_index("transaction_id")
    assert list(relabelled.loc["AAAAAAAAAAAAAAA1", "break_types"]) == ["rule_violation"]
