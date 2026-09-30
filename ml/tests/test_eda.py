import math

import pandas as pd
import pytest

from fraudml.eda import analysis as A
from fraudml.eda.report import render, write_report
from fraudml.pipeline import label_month, main
from fraudml.testing import write_month


def _txn(i: int, month: str, day: int) -> tuple:
    return (
        f"{i:016X}",
        f"ACC{i:04d}",
        f"2026-{month}-{day:02d}",
        "100.00",
        "USD",
        "US",
        "Vendor payment",
    )


def _join_map(rows) -> list[tuple]:
    return [(r[1], f"CUS-{r[1][3:].zfill(6)}", f"FA-{r[1][3:].zfill(6)}") for r in rows]


@pytest.fixture
def labelled(tmp_path, rules_path):
    """June is clean; July has one amount mismatch, one 7-day date gap and one txn missing in FA."""
    june = [_txn(i, "06", 1) for i in range(1, 5)]
    july = [_txn(i, "07", 3) for i in range(1, 7)]
    july_ma = [list(r) for r in july]
    july_ma[0][3] = "300.00"
    july_ma[1][2] = "2026-07-10"
    july_ma = [tuple(r) for r in july_ma]

    months = [
        ("202606", dict(gl_rows=june, ma_rows=june, fa_rows=june)),
        ("202607", dict(gl_rows=july, ma_rows=july_ma, fa_rows=july[:-1])),
    ]
    out = tmp_path / "processed"
    out.mkdir()
    for period, rows in months:
        month = write_month(
            tmp_path / period, join_map=_join_map(rows["gl_rows"]), period=period, **rows
        )
        p, df = label_month(month, rules_path)
        df.to_parquet(out / f"labelled_{p}.parquet", index=False)
    return out


def test_load_adds_period_and_segment_views(labelled):
    df = A.load_labelled(labelled)
    assert sorted(df["period"].unique()) == ["202606", "202607"]
    for col in ("currency", "amount", "weekday", "amount_band", "month_part", "account"):
        assert col in df.columns
    assert df["currency"].notna().all()


def test_overview_counts(labelled):
    ov = A.overview(A.load_labelled(labelled))
    assert ov.loc["202606", "suspicious"] == 0
    assert ov.loc["202607", "transactions"] == 6
    assert ov.loc["202607", "in_fa"] == 5
    assert ov.loc["202607", "suspicious"] == 3


def test_presence_and_break_types(labelled):
    df = A.load_labelled(labelled)
    patterns = A.presence_patterns(df)
    assert patterns.loc["GL+MA", "202607"] == 1
    types = A.break_type_counts(df)
    assert types.loc["amount_mismatch", "202607"] == 1
    assert types.loc["date_mismatch", "202607"] == 1
    assert types.loc["missing_in_fa", "202607"] == 1


def test_amount_and_date_deltas(labelled):
    df = A.load_labelled(labelled)
    deltas = A.amount_deltas(df)
    assert deltas["max_rel_delta"].iloc[0] == pytest.approx(200 / 300)
    assert A.date_deltas(df).tolist() == [7]


def test_wilson_interval_bounds():
    low, high = A.wilson_interval(5, 100)
    assert 0 < low < 0.05 < high < 1
    assert all(math.isnan(x) for x in A.wilson_interval(0, 0))


def test_segment_rates_and_spread(labelled):
    df = A.load_labelled(labelled)
    july = df[df["period"] == "202607"]
    rates = A.segment_rates(july, "currency")
    assert rates.loc["USD", "rate"] == pytest.approx(0.5)
    spread = A.segment_spread(july)
    assert list(spread.index) == A.SEGMENTS


def test_account_history_skips_month_after_clean_month(labelled):
    hist = A.account_history_effect(A.load_labelled(labelled))
    assert hist.empty


def test_psi_is_zero_for_identical_and_large_for_shifted():
    base = pd.Series(range(1000), dtype=float)
    assert A.psi(base, base) == pytest.approx(0, abs=1e-9)
    assert A.psi(base, base + 5000) > 0.25


def test_report_renders_sections_and_charts(labelled, tmp_path):
    html = render(A.load_labelled(labelled))
    for heading in (
        "Key findings",
        "Break types",
        "Does the rate vary by segment?",
        "Size of amount mismatches",
        "Drift against the first month",
    ):
        assert heading in html
    assert html.count("data:image/png;base64,") == 4
    out = write_report(labelled, tmp_path / "reports" / "eda.html")
    assert out.exists()


def test_load_without_parquet_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        A.load_labelled(tmp_path)


def test_cli_eda_writes_report_and_fails_cleanly(labelled, tmp_path):
    out = tmp_path / "eda.html"
    assert main(["eda", "--processed", str(labelled), "--out", str(out)]) == 0
    assert out.exists()
    assert main(["eda", "--processed", str(tmp_path / "nothing"), "--out", str(out)]) == 1
