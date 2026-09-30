import re

from app.core.security import create_access_token
from app.schemas.auth import UserCreate
from app.services import users

from .conftest import make_client

API = "/api/v1"


def record(**overrides) -> dict:
    base = {
        "account_key": "ACC0001",
        "transaction_date": "2026-08-20",
        "amount": 1500.25,
        "currency": "USD",
        "country": "US",
        "description": "Vendor payment",
    }
    return base | overrides


def submission(transaction_id="ABCDEF0123456789", **overrides) -> dict:
    """A GL record with matching MA and FA records."""
    counterparts = {
        "ma": record(account_key="CUS-000001"),
        "fa": record(account_key="FA-000001"),
    }
    body = record() | {"transaction_id": transaction_id, "counterparts": counterparts}
    return body | overrides


def test_matching_records_score_low(client, loaded, auth):
    resp = client.post(f"{API}/predictions", json=submission(), headers=auth())
    assert resp.status_code == 201
    body = resp.json()
    assert body["break_types"] == [] and body["rule_hits"] == []
    assert body["risk_band"] == "low" and body["risk_score"] < 40
    assert body["exposure_usd"] == 0 and body["priority"] <= body["risk_score"]
    assert body["created"] is True and body["in_systems"] == ["gl", "ma", "fa"]
    assert body["model_version"] == "model_v1" and body["latency_ms"] > 0


def test_amount_mismatch_scores_high_with_reasons(client, loaded, auth):
    body = submission()
    body["counterparts"]["ma"]["amount"] = 4500.25
    result = client.post(f"{API}/predictions", json=body, headers=auth()).json()
    assert result["break_types"] == ["amount_mismatch"]
    assert result["risk_score"] >= 70 and result["risk_band"] in ("high", "critical")
    assert result["exposure_usd"] == 3000.0  # the difference, in USD
    assert "GL 1,500.25, MA 4,500.25, FA 1,500.25" in result["rule_hits"][0]["reason"]
    assert result["top_factors"], "a high score comes with its main factors"


def test_records_arriving_later_are_linked_and_rescored(client, loaded, auth):
    gl_only = record() | {"transaction_id": "ABCDEF0123456790"}
    first = client.post(f"{API}/predictions", json=gl_only, headers=auth()).json()
    assert first["break_types"] == ["missing_in_ma", "missing_in_fa"]
    assert [h["reason"] for h in first["rule_hits"]] == ["Not found in MA.", "Not found in FA."]
    assert first["exposure_usd"] == 1500.25  # the whole amount is at stake

    later = record(account_key="CUS-000001") | {
        "transaction_id": "ABCDEF0123456790",
        "source_system": "ma",
        "counterparts": {"fa": record(account_key="FA-000001")},
    }
    resp = client.post(f"{API}/predictions", json=later, headers=auth())
    assert resp.status_code == 201
    second = resp.json()
    assert second["created"] is False and second["in_systems"] == ["gl", "ma", "fa"]
    assert second["break_types"] == []

    again = client.post(f"{API}/predictions", json=later, headers=auth("analyst2"))
    assert again.status_code == 409
    assert again.json()["detail"] == "Transaction ABCDEF0123456790 already has a MA/FA record"

    detail = client.get(f"{API}/transactions/ABCDEF0123456790", headers=auth()).json()
    assert [p["id"] for p in detail["predictions"]] == [second["id"], first["id"]]
    assert detail["risk_score"] == second["risk_score"]


def test_transaction_id_is_generated_when_missing(client, loaded, auth):
    body = submission()
    del body["transaction_id"]
    result = client.post(f"{API}/predictions", json=body, headers=auth()).json()
    assert re.fullmatch(r"[0-9A-F]{16}", result["transaction_id"])


def test_business_rule_breaches_are_scored_not_rejected(client, loaded, auth):
    body = submission(currency="XYZ", description="Fee")  # R05 currency, R07 description
    resp = client.post(f"{API}/predictions", json=body, headers=auth())
    assert resp.status_code == 201
    result = resp.json()
    assert "rule_violation" in result["break_types"]
    assert result["risk_score"] >= 90
    reason = next(h["reason"] for h in result["rule_hits"] if h["break_type"] == "rule_violation")
    assert "R05" in reason and "R07" in reason
    # the GL currency differs from MA and FA, which is a break of its own
    assert "currency_mismatch" in result["break_types"]


def test_unknown_account_is_flagged_and_join_map_falls_back_to_earlier_month(client, loaded, auth):
    unknown = submission(account_key="ACC9999")
    result = client.post(f"{API}/predictions", json=unknown, headers=auth()).json()
    assert "unmapped_account" in result["break_types"]

    september = submission(transaction_id="ABCDEF0123456791", transaction_date="2026-09-02")
    for system in ("ma", "fa"):
        september["counterparts"][system]["transaction_date"] = "2026-09-02"
    result = client.post(f"{API}/predictions", json=september, headers=auth()).json()
    assert result["break_types"] == []  # mapped through August's join map


def test_invalid_payloads_are_rejected(client, loaded, auth):
    cases = [
        submission(transaction_date="2026-13-01"),
        submission(amount="inf"),
        submission(amount=None),
        submission(transaction_id="has spaces"),
        submission(source_system="xx"),
        submission(unexpected="field") | {"counterparts": {"ma": record(extra=1)}},
        submission(counterparts={"gl": record()}),  # repeats the source system
    ]
    for body in cases:
        assert client.post(f"{API}/predictions", json=body, headers=auth()).status_code == 422


def test_batch_scores_each_item_on_its_own(client, loaded, auth):
    items = [
        submission("BA7C000000000001"),
        submission("BA7C000000000001"),  # same GL record again: conflict
        submission("BA7C000000000002", amount=10.0),
    ]
    resp = client.post(f"{API}/predictions/batch", json={"transactions": items}, headers=auth())
    assert resp.status_code == 200
    body = resp.json()
    assert (body["scored"], body["failed"]) == (2, 1)
    assert [i["status"] for i in body["items"]] == ["scored", "error", "scored"]
    assert body["items"][1]["status_code"] == 409
    stored = client.get(f"{API}/transactions?search=BA7C", headers=auth()).json()
    assert stored["total"] == 2

    too_many = {"transactions": [submission(f"BA7C00000000001{i}") for i in range(6)]}
    resp = client.post(f"{API}/predictions/batch", json=too_many, headers=auth())
    assert resp.status_code == 400  # settings.batch_max_items is 5 in tests


def test_get_prediction(client, loaded, auth):
    created = client.post(f"{API}/predictions", json=submission(), headers=auth()).json()
    resp = client.get(f"{API}/predictions/{created['id']}", headers=auth("approver"))
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "ABCDEF0123456789"
    assert client.get(f"{API}/predictions/999999", headers=auth()).status_code == 404


def test_scoring_needs_the_analyst_or_admin_role(client, loaded, auth):
    def post(headers=None):
        return client.post(f"{API}/predictions", json=submission(), headers=headers)

    assert post(auth("approver")).status_code == 403
    assert post().status_code == 401
    assert post(auth("admin")).status_code == 201


def test_without_a_model_scoring_is_unavailable(settings, tmp_path, dataset):
    empty = settings.model_copy(update={"model_dir": tmp_path / "no-models"})
    with make_client(empty) as client:
        ready = client.get(f"{API}/ready")
        assert ready.status_code == 503 and ready.json()["model"] is None
        with client.app.state.sessionmaker() as db:
            data = UserCreate(email="a@example.com", password="x" * 12, role="analyst")
            user = users.create_user(db, empty, data, None)
        token = create_access_token(user.id, user.role, empty.jwt_secret.get_secret_value(), 5)
        resp = client.post(
            f"{API}/predictions",
            json=submission(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 503
        assert "No active model" in resp.json()["detail"]
