from datetime import UTC, datetime, timedelta

import jwt

from .conftest import PASSWORD

API = "/api/v1"


def _login(client, email, password):
    return client.post(f"{API}/auth/login", data={"username": email, "password": password})


def test_health_and_ready(client, users):
    assert client.get(f"{API}/health").json() == {"status": "ok"}
    ready = client.get(f"{API}/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "database": True,
        "model": "model_v1",
        "rules": True,
    }


def test_login_returns_a_token_for_the_user(client, users):
    resp = _login(client, "Analyst@Example.com", PASSWORD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"]["email"] == "analyst@example.com"
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["role"] == "analyst"


def test_wrong_password_and_unknown_email_get_the_same_401(client, users):
    wrong = _login(client, "analyst@example.com", "not-the-password")
    unknown = _login(client, "nobody@example.com", PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password"}


def test_deactivated_user_cannot_log_in_or_use_a_token(client, users, auth):
    token = auth("analyst2")
    resp = client.patch(
        f"{API}/users/{users['analyst2'].id}", json={"is_active": False}, headers=auth("admin")
    )
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    assert _login(client, "analyst2@example.com", PASSWORD).status_code == 403
    assert client.get(f"{API}/auth/me", headers=token).status_code == 401


def test_missing_bad_and_expired_tokens_are_rejected(client, users, settings):
    assert client.get(f"{API}/auth/me").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get(f"{API}/auth/me", headers=bad).status_code == 401
    expired = jwt.encode(
        {"sub": str(users["analyst"].id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "another-secret" * 4, algorithm="HS256")
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_admin_creates_and_updates_users(client, users, auth):
    admin = auth("admin")
    new = {"email": "New.Person@Example.com", "password": "a-long-password-1", "role": "approver"}
    resp = client.post(f"{API}/users", json=new, headers=admin)
    assert resp.status_code == 201
    created = resp.json()
    assert created["email"] == "new.person@example.com" and "password" not in str(created)
    assert client.post(f"{API}/users", json=new, headers=admin).status_code == 409

    resp = client.patch(f"{API}/users/{created['id']}", json={"role": "analyst"}, headers=admin)
    assert resp.json()["role"] == "analyst"
    assert _login(client, "new.person@example.com", "a-long-password-1").status_code == 200
    assert len(client.get(f"{API}/users", headers=admin).json()) == 5

    audit = client.get(f"{API}/audit?entity=user", headers=admin).json()
    assert [a["action"] for a in audit["items"]][:2] == ["user.update", "user.create"]
    assert "password" not in str(audit["items"][1]["after"])


def test_admins_cannot_lock_themselves_out(client, users, auth):
    admin_id = users["admin"].id
    for change in ({"role": "analyst"}, {"is_active": False}):
        resp = client.patch(f"{API}/users/{admin_id}", json=change, headers=auth("admin"))
        assert resp.status_code == 409


def test_user_admin_needs_the_admin_role(client, users, auth):
    for name in ("analyst", "approver"):
        assert client.get(f"{API}/users", headers=auth(name)).status_code == 403
    assert client.patch(f"{API}/users/999", json={}, headers=auth("admin")).status_code == 404


def test_password_rules(client, users, auth):
    base = {"email": "p@example.com", "role": "analyst"}
    short = client.post(f"{API}/users", json=base | {"password": "short"}, headers=auth("admin"))
    assert short.status_code == 422
    long = client.post(
        f"{API}/users", json=base | {"password": "é" * 40}, headers=auth("admin")
    )  # 80 bytes: more than bcrypt can hash
    assert long.status_code == 422
    assert "72 bytes" in long.text


def test_request_id_is_echoed_or_generated(client):
    resp = client.get(f"{API}/health", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"
    generated = client.get(f"{API}/health", headers={"X-Request-ID": "bad id\n"})
    assert len(generated.headers["X-Request-ID"]) == 32
