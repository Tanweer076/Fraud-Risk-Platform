import pandas as pd
import pytest

from fraudml.features.build import ALL_FEATURES, GROUPS, build_features
from fraudml.pipeline import label_month
from fraudml.testing import BASE, JOIN_MAP, write_month


def _features(tmp_path, rules_path, **kwargs):
    _, labelled = label_month(write_month(tmp_path, **kwargs), rules_path)
    labelled["period"] = "202607"
    return labelled.set_index("transaction_id"), build_features(labelled).set_axis(
        labelled["transaction_id"]
    )


def _with(row_index: int, rows=BASE, **changes):
    rows = [list(r) for r in rows]
    fields = ["id", "acc", "date", "amount", "ccy", "country", "desc"]
    for key, value in changes.items():
        rows[row_index][fields.index(key)] = value
    return [tuple(r) for r in rows]


def test_columns_follow_feature_list_and_groups_cover_it(tmp_path, rules_path):
    _, X = _features(tmp_path, rules_path)
    assert list(X.columns) == ALL_FEATURES
    assert sorted(sum(GROUPS.values(), [])) == sorted(ALL_FEATURES)


def test_matching_systems_have_zero_deviation(tmp_path, rules_path):
    _, X = _features(tmp_path, rules_path)
    assert (X["n_systems"] == 3).all()
    assert (X["max_amt_reldiff"] == 0).all()
    assert (X["max_date_gap_days"] == 0).all()
    assert (X["n_currencies"] == 1).all()
    assert (X[["account_unmapped", "key_mismatch", "n_rule_violations"]] == 0).all().all()


def test_cross_system_deviations(tmp_path, rules_path):
    ma = _with(0, amount="300.00")
    ma = _with(1, rows=ma, date="2026-07-14")
    fa = _with(2, ccy="USD")
    _, X = _features(tmp_path, rules_path, ma_rows=ma, fa_rows=fa)
    first, second, third = X.index
    assert X.loc[first, "amt_reldiff_gl_ma"] == pytest.approx(200 / 300)
    assert X.loc[first, "max_amt_absdiff"] == pytest.approx(200)
    assert X.loc[second, "max_date_gap_days"] == 10
    assert X.loc[third, "n_currencies"] == 2


def test_missing_system_and_sign_conflict(tmp_path, rules_path):
    ma = _with(0, amount="-100.00")
    _, X = _features(tmp_path, rules_path, ma_rows=ma, fa_rows=BASE[1:])
    first = X.index[0]
    assert X.loc[first, "in_fa"] == 0
    assert X.loc[first, "n_systems"] == 2
    assert X.loc[first, "amount_sign_conflict"] == 1
    assert X.loc[first, "amount_negative"] == 1
    assert X.loc[first, "n_rule_violations"] == 1


def test_unmapped_account_and_out_of_period(tmp_path, rules_path):
    rows = _with(1, date="2026-08-02")
    _, X = _features(
        tmp_path, rules_path, gl_rows=rows, ma_rows=rows, fa_rows=rows, join_map=JOIN_MAP[1:]
    )
    first, second, _ = X.index
    assert X.loc[first, "account_unmapped"] == 1
    assert X.loc[second, "date_outside_period"] == 1
    assert X.loc[second, "n_rule_violations"] == 3  # PERIOD in each system


def _history_frame(rows, period="202607", suspicious=None):
    """Minimal linked-style frame for behavioural features."""
    df = pd.DataFrame(
        {
            "transaction_id": [r[0] for r in rows],
            "account_key_gl": [r[1] for r in rows],
            "period": period,
            "is_suspicious": suspicious or [False] * len(rows),
        }
    )
    for s in ("gl", "ma", "fa"):
        df[f"transaction_date_{s}"] = pd.to_datetime([r[2] for r in rows])
        df[f"amount_{s}"] = [float(r[3]) for r in rows]
        df[f"currency_{s}"] = [r[4] for r in rows]
    return df


def test_behavioural_features_only_use_earlier_days():
    from fraudml.features.build import _behavioural

    rows = [
        ("A1", "ACC0001", "2026-07-01", "100", "USD"),
        ("A2", "ACC0001", "2026-07-03", "300", "USD"),
        ("A3", "ACC0001", "2026-07-03", "500", "EUR"),  # same day as A2
        ("A4", "ACC0001", "2026-07-10", "1000", "USD"),
        ("B1", "ACC0002", "2026-07-05", "50", "USD"),
    ]
    f = _behavioural(_history_frame(rows), None).set_axis([r[0] for r in rows])
    assert f.loc["A1", "acct_prior_txn_count"] == 0
    assert f.loc["A2", "acct_prior_txn_count"] == 1  # A3 is same day, not earlier
    assert f.loc["A3", "acct_prior_txn_count"] == 1
    assert f.loc["A4", "acct_prior_txn_count"] == 3
    assert f.loc["A4", "acct_prior_mean_amount"] == pytest.approx(300)
    assert f.loc["A4", "acct_amount_to_prior_max"] == pytest.approx(2)
    assert f.loc["A4", "acct_days_since_last_txn"] == 7
    assert f.loc["A3", "acct_new_currency"] == 1
    assert f.loc["A4", "acct_new_currency"] == 0
    assert f.loc["B1", "acct_prior_txn_count"] == 0  # other account's history not used


def test_prior_month_breaks_use_earlier_months_only():
    from fraudml.features.build import _behavioural

    june = _history_frame([("J1", "ACC0001", "2026-06-10", "100", "USD")], "202606", [True])
    july = _history_frame(
        [
            ("K1", "ACC0001", "2026-07-02", "100", "USD"),
            ("K2", "ACC0001", "2026-07-09", "100", "USD"),
        ],
        "202607",
        [True, False],
    )
    f = _behavioural(july, june).set_axis(["K1", "K2"])
    assert f.loc["K1", "acct_prior_month_breaks"] == 1  # June break counts
    assert f.loc["K2", "acct_prior_month_breaks"] == 1  # K1's own-month label does not
    assert f.loc["K2", "acct_prior_txn_count"] == 2  # J1 from history plus K1
