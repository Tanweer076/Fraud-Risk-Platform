"""Rate limits (sign-in, scoring, uploads), the readiness check and the Prometheus endpoint."""

import re
import shutil

import pytest
from pydantic import ValidationError

from app.core.config import Settings

from .conftest import PASSWORD, auth_headers, create_users, load_month, make_client
from .test_predictions import submission

API = "/api/v1"


def limited(settings, **limits):
    return settings.model_copy(update={f"rate_limit_{k}": v for k, v in limits.items()})


def login(client, email="analyst@example.com", password=PASSWORD):
    return client.post(f"{API}/auth/login", data={"username": email, "password": password})


def assert_limited(resp, window=60):
    assert resp.status_code == 429
    retry_after = int(resp.headers["Retry-After"])
    assert 1 <= retry_after <= window
    assert resp.json()["detail"].startswith("Too many requests. Try again in")


def test_sign_in_attempts_are_limited_per_client(settings):
    with make_client(limited(settings, login="3/minute")) as client:
        create_users(client, settings)
        for email in ("analyst@example.com", "approver@example.com", "admin@example.com"):
            assert login(client, email, "wrong-password").status_code == 401
        assert_limited(login(client, "analyst2@example.com"))


def test_sign_in_attempts_are_limited_per_account(settings):
    with make_client(limited(settings, login_account="2/minute")) as client:
        create_users(client, settings)
        assert login(client, password="wrong-password").status_code == 401
        assert login(client, password="wrong-password").status_code == 401
        assert_limited(login(client))  # even with the right password, for now
        assert login(client, "approver@example.com").status_code == 200


def test_scoring_is_limited_per_user_and_a_batch_counts_each_transaction(settings):
    with make_client(limited(settings, scoring="3/minute")) as client:
        auth = auth_headers(create_users(client, settings), settings)
        batch = {"transactions": [submission(f"ABCDEF012345678{i}") for i in range(2)]}
        assert (
            client.post(f"{API}/predictions/batch", json=batch, headers=auth()).json()["scored"]
            == 2
        )
        one = client.post(f"{API}/predictions", json=submission("ABCDEF0123456799"), headers=auth())
        assert one.status_code == 201
        assert_limited(
            client.post(f"{API}/predictions", json=submission("ABCDEF0123456798"), headers=auth())
        )
        other = client.post(
            f"{API}/predictions", json=submission("ABCDEF0123456797"), headers=auth("admin")
        )
        assert other.status_code == 201


def test_month_uploads_are_limited_per_user(settings):
    files = {
        "gl": ("gl_report_202607.xml", b"<GLReport/>"),
        "fa": ("fa_report_202607.csv", b""),
        "join_map": ("join_map.txt", b""),
    }
    with make_client(limited(settings, upload="1/hour")) as client:
        auth = auth_headers(create_users(client, settings), settings)

        def upload():
            return client.post(
                f"{API}/ingestion/upload", data={"period": "202607"}, files=files, headers=auth()
            )

        assert upload().status_code == 400  # no MA given, but the attempt counts
        assert_limited(upload(), window=3600)


def test_limits_must_be_readable():
    with pytest.raises(ValidationError, match="rate_limit_scoring"):
        Settings(_env_file=None, jwt_secret="x" * 32, rate_limit_scoring="lots")
    assert Settings(_env_file=None, jwt_secret="x" * 32, rate_limit_login="").rate_limit_login == ""


def test_rules_put_in_place_after_startup_are_picked_up(settings, tmp_path):
    rules = tmp_path / "business_rules.txt"
    late = settings.model_copy(update={"rules_path": rules})
    with make_client(late) as client:
        auth = auth_headers(create_users(client, late), late)

        def score():
            return client.post(f"{API}/predictions", json=submission(), headers=auth())

        ready = client.get(f"{API}/ready")
        assert ready.status_code == 503 and ready.json()["rules"] is False
        assert score().status_code == 503

        shutil.copy(settings.rules_path, rules)
        assert client.get(f"{API}/ready").json()["status"] == "ready"
        assert score().status_code == 201


SAMPLE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>.*)\})? (?P<value>\S+)$")
LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def sample(text: str, name: str, **labels) -> float:
    """The value of one metric sample in Prometheus text format, or 0 if absent."""
    wanted = {k: str(v) for k, v in labels.items()}
    for line in text.splitlines():
        match = SAMPLE.match(line)
        if match and match["name"] == name and dict(LABEL.findall(match["labels"] or "")) == wanted:
            return float(match["value"])
    return 0.0


def test_metrics_count_requests_by_route_scores_and_refusals(settings):
    with make_client(limited(settings, login_account="1/minute")) as client:
        auth = auth_headers(create_users(client, settings), settings)
        before = client.get("/metrics").text

        client.get(f"{API}/transactions/NOPE", headers=auth())
        client.post(f"{API}/predictions", json=submission(), headers=auth())
        login(client, password="wrong-password")
        login(client, password="wrong-password")

        resp = client.get("/metrics")
        assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/plain")
        after = resp.text

        def grew(name, **labels):
            return sample(after, name, **labels) - sample(before, name, **labels)

        route = "/transactions/{transaction_id}"  # the template, within /api/v1
        assert grew("http_requests_total", method="GET", route=route, status="404") == 1
        assert grew("http_request_duration_seconds_count", method="GET", route=route) == 1
        scored = [
            grew("fraud_scored_transactions_total", source="api", band=band)
            for band in ("low", "medium", "high", "critical")
        ]
        assert sum(scored) == 1
        assert grew("fraud_risk_score_count", source="api") == 1
        assert grew("fraud_scoring_duration_seconds_count") == 1
        assert grew("fraud_rate_limited_total", scope="login_account") == 1
        assert sample(after, "fraud_active_model_info", version="model_v1") == 1
        assert "/metrics" not in client.get(f"{API}/openapi.json").json()["paths"]


def test_month_loads_are_counted(settings, dataset):
    with make_client(settings) as client:
        create_users(client, settings)
        before = client.get("/metrics").text
        load_month(client.app, settings, dataset / "raw" / "202607")
        after = client.get("/metrics").text
        loaded = sample(after, "fraud_ingestion_batches_total", status="succeeded") - sample(
            before, "fraud_ingestion_batches_total", status="succeeded"
        )
        assert loaded == 1
        scored = sum(
            sample(after, "fraud_scored_transactions_total", source="batch", band=band)
            - sample(before, "fraud_scored_transactions_total", source="batch", band=band)
            for band in ("low", "medium", "high", "critical")
        )
        assert scored == 300  # the synthetic month's transactions


def test_metrics_can_be_turned_off(settings):
    with make_client(settings.model_copy(update={"metrics_enabled": False})) as client:
        assert client.get("/metrics").status_code == 404
