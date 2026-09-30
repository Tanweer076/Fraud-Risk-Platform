from pathlib import Path

import pytest
from fraudml.ingest.ma_api import read_ma_embedded
from sqlalchemy import func, select

from app.models import AccountKeyMap, IngestionBatch, Prediction, Transaction
from app.services import ingestion

from .conftest import load_month, make_client

API = "/api/v1"


def _files(month: Path, period: str, ma: bool = True) -> dict:
    names = {
        "gl": f"gl_report_{period}.xml",
        "fa": f"fa_report_{period}.csv",
        "join_map": "join_map.txt",
    }
    if ma:
        names["ma"] = f"ma_api_server_{period}.py"
    return {key: (name, (month / name).read_bytes()) for key, name in names.items()}


def _upload(client, auth, dataset, period="202607", who="analyst", data=None, files=None):
    month = dataset / "raw" / period
    return client.post(
        f"{API}/ingestion/upload",
        data={"period": period} | (data or {}),
        files=files if files is not None else _files(month, period),
        headers=auth(who),
    )


def _count(client, model, **where):
    with client.app.state.sessionmaker() as db:
        stmt = select(func.count()).select_from(model)
        for key, value in where.items():
            stmt = stmt.where(getattr(model, key) == value)
        return db.scalar(stmt)


def test_upload_loads_links_scores_and_stores_a_month(client, users, auth, dataset):
    resp = _upload(client, auth, dataset)
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued" and resp.json()["method"] == "file"

    batch = client.get(f"{API}/ingestion/batches/{resp.json()['id']}", headers=auth()).json()
    assert batch["status"] == "succeeded", batch["error"]
    assert batch["records"] == {"gl": 300, "ma": 300, "fa": batch["records"]["fa"], "join_map": 40}
    assert batch["transactions_loaded"] == batch["transactions_scored"] == 300
    assert batch["summary"]["suspicious"] == 36
    assert batch["summary"]["model_version"] == "model_v1"
    assert sum(batch["summary"]["bands"].values()) == 300
    assert batch["duration_ms"] > 0 and batch["finished_at"] is not None

    assert _count(client, Transaction, period="202607") == 300
    assert _count(client, Prediction) == 300
    assert _count(client, AccountKeyMap, period="202607") == 40


def test_reloading_a_month_updates_in_place_and_keeps_review_outcomes(client, users, auth, dataset):
    _upload(client, auth, dataset)
    flagged = client.get(f"{API}/reviews/queue", headers=auth()).json()["items"][0]
    review = client.post(
        f"{API}/reviews",
        json={"transaction_id": flagged["transaction_id"], "decision": "confirmed"},
        headers=auth(),
    ).json()
    client.post(f"{API}/reviews/{review['id']}/approve", json={}, headers=auth("approver"))

    second = _upload(client, auth, dataset)
    assert second.status_code == 202
    assert _count(client, Transaction) == 300  # no duplicates
    assert _count(client, Prediction) == 600  # score history is kept
    assert _count(client, AccountKeyMap) == 40  # the month's join map is replaced
    detail = client.get(f"{API}/transactions/{flagged['transaction_id']}", headers=auth()).json()
    assert detail["review_outcome"] == "confirmed"
    assert len(detail["predictions"]) == 2


def test_history_from_earlier_months_is_used(client, users, auth, dataset):
    """Behavioural features see earlier months, so load order changes nothing for June."""
    for period in ("202606", "202607"):
        assert _upload(client, auth, dataset, period=period).status_code == 202
    batches = client.get(f"{API}/ingestion/batches", headers=auth()).json()
    assert batches["total"] == 2
    assert [b["period"] for b in batches["items"]] == ["202607", "202606"]
    assert {b["status"] for b in batches["items"]} == {"succeeded"}


def test_ma_can_be_pulled_from_an_allowed_api_host(client, users, auth, dataset, monkeypatch):
    month = dataset / "raw" / "202607"
    calls = []

    def fake_api(url):
        calls.append(url)
        return read_ma_embedded(month / "ma_api_server_202607.py")

    monkeypatch.setattr(ingestion, "read_ma_api", fake_api)
    resp = _upload(
        client,
        auth,
        dataset,
        data={"ma_url": "https://ma.example.com"},
        files=_files(month, "202607", ma=False),
    )
    assert resp.status_code == 202
    assert calls == ["https://ma.example.com"]
    batch = client.get(f"{API}/ingestion/batches/{resp.json()['id']}", headers=auth()).json()
    assert batch["method"] == "api" and batch["status"] == "succeeded"
    assert batch["files"]["ma"] == "https://ma.example.com"


@pytest.mark.parametrize(
    ("data", "drop_ma", "status", "message"),
    [
        ({}, True, 400, "either an MA file or ma_url"),
        ({"ma_url": "https://ma.example.com"}, False, 400, "not both"),
        ({"ma_url": "http://169.254.169.254/latest"}, True, 400, "not allowed"),
        ({"ma_url": "https://user:pw@ma.example.com"}, True, 400, "credentials"),
        ({"ma_url": "file:///etc/passwd"}, True, 400, "http(s)"),
        ({"period": "202613"}, False, 422, ""),
    ],
)
def test_upload_validation(client, users, auth, dataset, data, drop_ma, status, message):
    month = dataset / "raw" / "202607"
    resp = _upload(client, auth, dataset, data=data, files=_files(month, "202607", ma=not drop_ma))
    assert resp.status_code == status
    assert message in resp.text
    assert client.get(f"{API}/ingestion/batches", headers=auth()).json()["total"] == 0


def test_wrong_file_type_is_rejected(client, users, auth, dataset):
    files = _files(dataset / "raw" / "202607", "202607")
    files["gl"] = ("gl_report.csv", files["gl"][1])
    resp = _upload(client, auth, dataset, files=files)
    assert resp.status_code == 400 and ".xml" in resp.json()["detail"]


def test_a_broken_file_fails_the_batch_and_stores_nothing(client, users, auth, dataset):
    files = _files(dataset / "raw" / "202607", "202607")
    files["gl"] = ("gl_report_202607.xml", b"<GLReport><Transaction>")
    resp = _upload(client, auth, dataset, files=files)
    assert resp.status_code == 202
    batch = client.get(f"{API}/ingestion/batches/{resp.json()['id']}", headers=auth()).json()
    assert batch["status"] == "failed"
    assert "Cannot read GL XML" in batch["error"]
    assert _count(client, Transaction) == 0 and _count(client, AccountKeyMap) == 0


def test_oversized_upload_is_refused(client, users, auth, dataset, settings, monkeypatch):
    monkeypatch.setattr(client.app.state.settings, "max_upload_mb", 0)
    resp = _upload(client, auth, dataset)
    assert resp.status_code == 413
    batch = client.get(f"{API}/ingestion/batches", headers=auth()).json()["items"][0]
    assert batch["status"] == "failed"


def test_upload_needs_the_analyst_or_admin_role(client, users, auth, dataset):
    assert _upload(client, auth, dataset, who="approver").status_code == 403
    assert client.get(f"{API}/ingestion/batches/999", headers=auth()).status_code == 404


def test_without_a_model_months_load_unscored(settings, tmp_path, dataset):
    unscored = settings.model_copy(update={"model_dir": tmp_path / "none"})
    with make_client(unscored) as client:
        batch_id = load_month(client.app, unscored, dataset / "raw" / "202607")
        with client.app.state.sessionmaker() as db:
            batch = db.get(IngestionBatch, batch_id)
            assert batch.status == "succeeded"
            assert batch.transactions_loaded == 300 and batch.transactions_scored == 0
            assert batch.summary["note"] == "Not scored: no active model"
        assert _count(client, Prediction) == 0
        assert _count(client, Transaction, risk_score=None) == 300
