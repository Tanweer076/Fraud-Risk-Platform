import pandas as pd
import pytest
from fraudml.eda.analysis import load_labelled
from fraudml.labels.break_labeller import summarise

API = "/api/v1"


@pytest.fixture(scope="module")
def labelled(dataset) -> pd.DataFrame:
    return load_labelled(dataset / "processed")


def _get(shared, path, **params):
    resp = shared.client.get(f"{API}/analytics/{path}", params=params, headers=shared.auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_summary_matches_the_data(shared, labelled):
    body = _get(shared, "summary")
    assert body["periods"] == ["202606", "202607", "202608"]
    assert body["transactions"] == body["scored"] == len(labelled)
    assert body["suspicious"] == int(labelled["is_suspicious"].sum())
    assert sum(body["by_band"].values()) == len(labelled)
    assert body["high_or_critical"] == body["suspicious"]  # every break scores 70 or more
    assert body["review_queue"] == body["suspicious"]
    assert body["exposure_usd_at_risk"] > 0
    assert (body["pending_approval"], body["confirmed"], body["false_positive"]) == (0, 0, 0)

    june = _get(shared, "summary", period="202606")
    assert june["transactions"] == int((labelled["period"] == "202606").sum())
    assert june["suspicious"] == 0 and june["exposure_usd_at_risk"] == 0


def test_risk_distribution_adds_up(shared, labelled):
    body = _get(shared, "risk-distribution", period="202608")
    aug = labelled[labelled["period"] == "202608"]
    assert len(body["bins"]) == 10
    assert (body["bins"][0]["score_from"], body["bins"][-1]["score_to"]) == (0, 100)
    assert sum(b["count"] for b in body["bins"]) == len(aug)
    assert [b["band"] for b in body["bands"]] == ["low", "medium", "high", "critical"]
    assert sum(b["share"] for b in body["bands"]) == pytest.approx(1.0, abs=1e-3)


def test_trends_by_month_and_day(shared, labelled):
    months = _get(shared, "trends", granularity="month")
    assert [m["bucket"] for m in months] == ["202606", "202607", "202608"]
    for point in months:
        group = labelled[labelled["period"] == point["bucket"]]
        assert point["transactions"] == len(group)
        assert point["suspicious"] == int(group["is_suspicious"].sum())
    days = _get(shared, "trends", period="202607")
    assert sum(d["transactions"] for d in days) == int((labelled["period"] == "202607").sum())
    assert [d["bucket"] for d in days] == sorted(d["bucket"] for d in days)


def test_breakdown_by_break_type_matches_the_labels(shared, labelled):
    rows = _get(shared, "breakdown", by="break_type")
    expected = {k: v for k, v in summarise(labelled)["by_break_type"].items() if v}
    assert {r["key"]: r["transactions"] for r in rows} == expected
    assert all(r["suspicious_rate"] == 1.0 for r in rows)


@pytest.mark.parametrize("by", ["currency", "country", "description", "period", "band"])
def test_breakdown_segments_cover_every_transaction(shared, labelled, by):
    rows = _get(shared, "breakdown", by=by)
    assert sum(r["transactions"] for r in rows) == len(labelled)
    suspicious = [r["suspicious"] for r in rows]
    assert suspicious == sorted(suspicious, reverse=True)


def test_top_accounts(shared, labelled):
    rows = _get(shared, "top-accounts", limit=5)
    assert 0 < len(rows) <= 5
    counts = labelled[labelled["is_suspicious"]].groupby("account").size()
    for row in rows:
        assert row["suspicious"] == counts[row["account"]]
    assert [r["suspicious"] for r in rows] == sorted((r["suspicious"] for r in rows), reverse=True)


def test_bad_analytics_parameters(shared):
    for path, params in [
        ("breakdown", {"by": "password"}),
        ("breakdown", {}),
        ("trends", {"granularity": "hour"}),
        ("summary", {"period": "June"}),
        ("top-accounts", {"limit": 0}),
    ]:
        resp = shared.client.get(f"{API}/analytics/{path}", params=params, headers=shared.auth())
        assert resp.status_code == 422, (path, params)
