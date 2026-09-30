import pandas as pd
import pytest
from fraudml.eda.analysis import load_labelled

API = "/api/v1"


@pytest.fixture(scope="module")
def labelled(dataset) -> pd.DataFrame:
    return load_labelled(dataset / "processed")


def _list(shared, **params):
    resp = shared.client.get(f"{API}/transactions", params=params, headers=shared.auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_every_transaction_is_stored_and_scored(shared, labelled):
    body = _list(shared, page_size=1)
    assert body["total"] == len(labelled)
    for period, group in labelled.groupby("period"):
        assert _list(shared, period=period, page_size=1)["total"] == len(group)
        suspicious = _list(shared, period=period, suspicious=True, page_size=1)["total"]
        assert suspicious == int(group["is_suspicious"].sum())
    assert _list(shared, max_score=100, page_size=1)["total"] == len(labelled)  # all scored


# The break types fraudml.testing.make_dataset injects.
SYNTHETIC_BREAKS = [
    "amount_mismatch",
    "date_mismatch",
    "currency_mismatch",
    "missing_in_fa",
    "rule_violation",
]


@pytest.mark.parametrize("break_type", SYNTHETIC_BREAKS)
def test_filter_by_break_type(shared, labelled, break_type):
    expected = int(labelled[f"brk_{break_type}"].sum())
    assert expected > 0
    body = _list(shared, break_type=break_type, page_size=500)
    assert body["total"] == expected
    assert all(break_type in t["break_types"] for t in body["items"])


def test_filters_combine(shared, labelled):
    aug = labelled[labelled["period"] == "202608"]
    usd = aug[aug["currency"] == "USD"]
    body = _list(shared, period="202608", currency="USD", page_size=1)
    assert body["total"] == len(usd)
    high = _list(shared, period="202608", band=["high", "critical"], page_size=500)
    assert high["total"] == int(aug["is_suspicious"].sum())
    assert all(t["risk_score"] >= 70 for t in high["items"])
    low = _list(shared, band="low", min_score=0, max_score=39, page_size=1)
    assert low["total"] == len(labelled) - int(labelled["is_suspicious"].sum())


def test_account_date_and_search_filters(shared, labelled):
    account = labelled["account"].value_counts().index[0]
    body = _list(shared, account=account, page_size=500)
    assert body["total"] == int((labelled["account"] == account).sum())
    assert {t["gl_account_id"] for t in body["items"]} == {account}

    days = _list(shared, date_from="2026-08-01", date_to="2026-08-10", page_size=500)
    assert all("2026-08-01" <= t["transaction_date"] <= "2026-08-10" for t in days["items"])

    one = labelled["transaction_id"].iloc[0]
    assert _list(shared, search=one.lower())["items"][0]["transaction_id"] == one
    assert _list(shared, search="%_")["total"] == 0  # wildcards are matched literally


def test_sorting_and_paging(shared):
    first = _list(shared, sort="-priority,-risk_score", page=1, page_size=20)
    second = _list(shared, sort="-priority,-risk_score", page=2, page_size=20)
    priorities = [t["priority"] for t in first["items"] + second["items"]]
    assert priorities == sorted(priorities, reverse=True)
    assert not {t["transaction_id"] for t in first["items"]} & {
        t["transaction_id"] for t in second["items"]
    }
    amounts = [t["amount"] for t in _list(shared, sort="amount", page_size=50)["items"]]
    assert amounts == sorted(amounts)


def test_default_order_breaks_priority_ties_by_money_at_stake(shared):
    items = _list(shared, suspicious=True, page_size=500)["items"]
    keys = [(t["priority"], t["risk_score"], t["exposure_usd"] or 0) for t in items]
    assert keys == sorted(keys, reverse=True)


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "password"},
        {"page": 0},
        {"page_size": 501},
        {"band": "extreme"},
        {"period": "2026"},
    ],
)
def test_bad_list_parameters(shared, params):
    resp = shared.client.get(f"{API}/transactions", params=params, headers=shared.auth())
    assert resp.status_code in (400, 422)


def test_detail_shows_each_system_and_the_score_history(shared, labelled):
    missing_fa = labelled[labelled["brk_missing_in_fa"]].iloc[0]
    resp = shared.client.get(
        f"{API}/transactions/{missing_fa['transaction_id']}", headers=shared.auth("approver")
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["systems"]["fa"] is None
    gl = detail["systems"]["gl"]
    assert gl["account_key"] == missing_fa["account_key_gl"]
    assert gl["amount"] == pytest.approx(missing_fa["amount_gl"])
    assert detail["systems"]["ma"]["account_key"].startswith("CUS-")
    assert detail["expected_fa_key"].startswith("FA-")
    assert detail["break_types"] == ["missing_in_fa"]
    assert len(detail["predictions"]) == 1
    prediction = detail["predictions"][0]
    assert prediction["rule_hits"] == [
        {"break_type": "missing_in_fa", "reason": "Not found in FA."}
    ]
    assert prediction["top_factors"], "flagged rows are explained"
    assert detail["reviews"] == []


def test_low_risk_rows_are_not_explained_in_batch(shared, labelled):
    clean = labelled[~labelled["is_suspicious"]].iloc[0]
    detail = shared.client.get(
        f"{API}/transactions/{clean['transaction_id']}", headers=shared.auth()
    ).json()
    assert detail["risk_score"] < 40
    assert detail["predictions"][0]["top_factors"] == []


def test_unknown_transaction_is_404(shared):
    resp = shared.client.get(f"{API}/transactions/NOPE", headers=shared.auth())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Transaction NOPE not found"}


def test_listing_needs_a_login(shared):
    assert shared.client.get(f"{API}/transactions").status_code == 401
