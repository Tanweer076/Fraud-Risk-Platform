"""Test fixtures. Tests run against a real PostgreSQL database.

TEST_DATABASE_URL points at a database the tests may wipe (default: fraud_test on localhost).
A small synthetic dataset is generated and a model trained on it once per session.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from fraudml.models.train import train
from fraudml.testing import RULES, make_dataset
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.core.security import create_access_token
from app.main import create_app
from app.schemas.auth import UserCreate
from app.services import ingestion
from app.services import users as user_service

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://fraud:fraud@localhost:5432/fraud_test"
)
BACKEND_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "correct-horse-battery"
PERIODS = ("202606", "202607", "202608")
TABLES = (
    "audit_log",
    "reviews",
    "predictions",
    "transactions",
    "account_key_map",
    "ingestion_batches",
    "model_versions",
    "users",
)


@pytest.fixture(scope="session")
def database_url() -> str:
    """A freshly migrated database (runs the Alembic migration itself)."""
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def dataset(tmp_path_factory) -> Path:
    """Synthetic raw months (raw/YYYYMM/), rules and a trained model (artifacts/model_v1)."""
    root = tmp_path_factory.mktemp("dataset")
    rules = root / "business_rules.txt"
    rules.write_text(RULES)
    processed = make_dataset(root, rules)
    train(processed, root / "artifacts")
    return root


@pytest.fixture(scope="session")
def settings(database_url, dataset, tmp_path_factory) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        log_level="WARNING",
        database_url=database_url,
        jwt_secret="test-secret-that-is-long-enough-0123456789",
        bcrypt_rounds=4,
        model_dir=dataset / "artifacts",
        rules_path=dataset / "business_rules.txt",
        upload_dir=tmp_path_factory.mktemp("uploads"),
        ma_api_allowed_hosts=["ma.example.com"],
        batch_max_items=5,
        # Off here; tests/test_limits_and_metrics.py turns them on with small numbers.
        rate_limit_login="",
        rate_limit_login_account="",
        rate_limit_scoring="",
        rate_limit_upload="",
    )


def reset_database(url: str) -> None:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    engine.dispose()


def make_client(settings: Settings):
    reset_database(settings.database_url)
    return TestClient(create_app(settings))


@pytest.fixture
def client(settings):
    with make_client(settings) as c:
        yield c


def create_users(client, settings) -> dict:
    """analyst, analyst2, approver and admin, all with PASSWORD."""
    made = {}
    with client.app.state.sessionmaker() as db:
        for name, role in (
            ("analyst", "analyst"),
            ("analyst2", "analyst"),
            ("approver", "approver"),
            ("admin", "admin"),
        ):
            data = UserCreate(email=f"{name}@example.com", password=PASSWORD, role=role)
            made[name] = user_service.create_user(db, settings, data, actor=None)
    return made


def auth_headers(users: dict, settings: Settings):
    """auth("approver") -> Authorization header for that user."""

    def headers(name: str = "analyst") -> dict:
        user = users[name]
        token = create_access_token(user.id, user.role, settings.jwt_secret.get_secret_value(), 60)
        return {"Authorization": f"Bearer {token}"}

    return headers


def load_month(app, settings, month_dir: Path) -> int:
    period, paths = ingestion.find_month_files(month_dir)
    with app.state.sessionmaker() as db:
        files = {k: p.name for k, p in paths.items()}
        batch_id = ingestion.create_batch(db, period, "cli", files, None).id
    ingestion.run_batch(
        app.state.sessionmaker, app.state.registry, app.state.rules, settings, batch_id, paths
    )
    return batch_id


def load_all(app, settings, dataset: Path) -> None:
    for period in PERIODS:
        load_month(app, settings, dataset / "raw" / period)


@pytest.fixture
def users(client, settings) -> dict:
    return create_users(client, settings)


@pytest.fixture
def auth(users, settings):
    return auth_headers(users, settings)


@pytest.fixture
def users_on(settings):
    """users_on(client): the standard users, for a client a test made itself."""
    return lambda client: create_users(client, settings)


@pytest.fixture
def loaded(client, settings, dataset, users):
    """The three synthetic months loaded and scored."""
    load_all(client.app, settings, dataset)
    return dataset


@dataclass
class Shared:
    client: TestClient
    auth: Callable[..., dict]
    users: dict


@pytest.fixture(scope="module")
def shared(settings, dataset):
    """Loaded data shared by a whole module, for tests that only read."""
    with make_client(settings) as client:
        users = create_users(client, settings)
        load_all(client.app, settings, dataset)
        yield Shared(client, auth_headers(users, settings), users)


@pytest.fixture
def model_dir_copy(dataset, tmp_path) -> Path:
    """A private copy of the artifacts folder, for tests that add or remove models."""
    target = tmp_path / "artifacts"
    shutil.copytree(dataset / "artifacts", target)
    return target
