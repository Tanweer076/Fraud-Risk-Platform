import pytest

from app.cli import main
from app.core.config import get_settings

from .conftest import reset_database


@pytest.fixture
def cli_env(settings, monkeypatch):
    """Point the CLI's environment-based settings at the test database and dataset."""
    reset_database(settings.database_url)
    env = {
        "DATABASE_URL": settings.database_url,
        "JWT_SECRET": settings.jwt_secret.get_secret_value(),
        "MODEL_DIR": str(settings.model_dir),
        "RULES_PATH": str(settings.rules_path),
        "BCRYPT_ROUNDS": "4",
        "LOG_LEVEL": "WARNING",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_user(cli_env, capsys, monkeypatch):
    monkeypatch.setenv("FRAUDAPI_PASSWORD", "a-long-password-1")
    assert main(["create-user", "--email", "Boss@Example.com", "--role", "admin"]) == 0
    assert "Created admin boss@example.com" in capsys.readouterr().out
    assert main(["create-user", "--email", "boss@example.com", "--role", "admin"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_create_user_does_not_echo_a_rejected_password(cli_env, capsys):
    args = ["create-user", "--email", "x@example.com", "--role", "analyst"]
    assert main([*args, "--password", "s3cret"]) == 1
    err = capsys.readouterr().err
    assert "at least 12 characters" in err and "s3cret" not in err


def test_ingest_and_sync_models(cli_env, dataset, capsys):
    assert main(["sync-models"]) == 0
    assert "Active model: model_v1" in capsys.readouterr().out
    months = [str(dataset / "raw" / p) for p in ("202606", "202607")]
    assert main(["ingest", "--month-dir", months[0], "--month-dir", months[1]]) == 0
    out = capsys.readouterr().out
    assert "202606: succeeded, 300 transactions, 0 suspicious, 300 scored" in out
    assert "202607: succeeded, 300 transactions, 36 suspicious" in out
    assert main(["ingest", "--month-dir", str(dataset)]) == 1
    assert "Expected one gl_report_*.xml" in capsys.readouterr().err
