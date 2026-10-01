"""Dashboard sign-in: the token lives in an HttpOnly cookie, and writes need X-Requested-With."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import PASSWORD, reset_database

API = "/api/v1"
CSRF = {"X-Requested-With": "fetch"}


def https_client(settings) -> TestClient:
    """Secure cookies are only sent back over HTTPS, as in production."""
    reset_database(settings.database_url)
    return TestClient(create_app(settings), base_url="https://testserver")


def sign_in(client, email="admin@example.com", headers=CSRF):
    return client.post(
        f"{API}/auth/session",
        data={"username": email, "password": PASSWORD},
        headers=headers,
    )


def test_signing_in_sets_an_httponly_cookie_instead_of_returning_the_token(settings, users_on):
    with https_client(settings) as client:
        users_on(client)
        resp = sign_in(client)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"user", "expires_at"} and body["user"]["role"] == "admin"
        expires = datetime.fromisoformat(body["expires_at"])
        assert abs(expires - (datetime.now(UTC) + timedelta(hours=1))) < timedelta(seconds=5)

        cookie = resp.headers["set-cookie"]
        assert cookie.startswith("fraud_session=")
        for attribute in ("HttpOnly", "Max-Age=3600", "Path=/api", "SameSite=strict", "Secure"):
            assert attribute in cookie

        session = client.get(f"{API}/auth/session")
        assert session.status_code == 200 and session.json()["user"]["email"] == (
            "admin@example.com"
        )
        assert client.get(f"{API}/transactions").status_code == 200


def test_signing_in_needs_the_header_so_other_sites_cannot_post_the_form(settings, users_on):
    with https_client(settings) as client:
        users_on(client)
        resp = sign_in(client, headers={})
        assert resp.status_code == 403 and "X-Requested-With" in resp.json()["detail"]
        assert "set-cookie" not in resp.headers
        assert sign_in(client, headers=CSRF).status_code == 200


def test_writes_with_the_cookie_need_the_header(settings, users_on):
    with https_client(settings) as client:
        users_on(client)
        sign_in(client)
        refused = client.post(f"{API}/models/sync")
        assert refused.status_code == 403 and "X-Requested-With" in refused.json()["detail"]
        assert client.post(f"{API}/models/sync", headers=CSRF).status_code == 200


def test_a_bearer_token_needs_no_header(client, auth):
    assert client.post(f"{API}/models/sync", headers=auth("admin")).status_code == 200


def test_signing_out_drops_the_cookie(settings, users_on):
    with https_client(settings) as client:
        users_on(client)
        sign_in(client)
        assert client.delete(f"{API}/auth/session").status_code == 403
        resp = client.delete(f"{API}/auth/session", headers=CSRF)
        assert resp.status_code == 204
        assert "fraud_session=" in resp.headers["set-cookie"]
        assert "Max-Age=0" in resp.headers["set-cookie"]
        assert client.get(f"{API}/auth/session").status_code == 401


def test_without_a_session_the_dashboard_is_told_to_sign_in(client):
    resp = client.get(f"{API}/auth/session")
    assert resp.status_code == 401 and resp.json() == {"detail": "Not authenticated"}


def test_a_wrong_password_sets_no_cookie(settings, users_on):
    with https_client(settings) as client:
        users_on(client)
        resp = client.post(
            f"{API}/auth/session",
            data={"username": "admin@example.com", "password": "not-the-password"},
            headers=CSRF,
        )
        assert resp.status_code == 401 and "set-cookie" not in resp.headers


def test_plain_http_cookies_can_be_allowed_for_local_runs(settings, users_on):
    local = settings.model_copy(update={"cookie_secure": False})
    reset_database(local.database_url)
    with TestClient(create_app(local)) as client:
        users_on(client)
        resp = sign_in(client)
        assert "Secure" not in resp.headers["set-cookie"]
        assert client.get(f"{API}/auth/session").status_code == 200
