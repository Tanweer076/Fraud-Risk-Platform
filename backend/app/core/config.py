"""Settings read from environment variables (or a .env file). No secrets live in code."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from limits import parse as parse_limit
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Only the database URL, for tools such as Alembic that need nothing else."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fraud:fraud@localhost:5432/fraud"


class Settings(DatabaseSettings):
    app_name: str = "Fraud Risk Platform API"
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(60, ge=1, le=24 * 60)
    bcrypt_rounds: int = Field(12, ge=4, le=16)
    # The dashboard keeps its token in this HttpOnly cookie; API clients send a Bearer header.
    session_cookie_name: str = "fraud_session"
    # Secure cookies are only sent over HTTPS. Turn off only for plain-HTTP local runs.
    cookie_secure: bool = True

    # Rate limits such as "10/minute", counted in each API process. Empty turns one off.
    rate_limit_login: str = "10/minute"  # sign-in attempts per client IP
    rate_limit_login_account: str = "5/minute"  # sign-in attempts per email
    rate_limit_scoring: str = "120/minute"  # transactions scored per user
    rate_limit_upload: str = "20/hour"  # month uploads per user
    metrics_enabled: bool = True

    model_dir: Path = Path("ml/artifacts")
    rules_path: Path = Path("data/raw/OneRecon_DataSet/business_rules.txt")
    upload_dir: Path = Path("data/uploads")
    max_upload_mb: int = Field(50, ge=1)

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    # Hosts the MA REST API may be pulled from. Empty disables pulling by URL.
    ma_api_allowed_hosts: Annotated[list[str], NoDecode] = []

    review_min_score: int = Field(70, ge=0, le=100)
    explain_min_score: int = Field(40, ge=0, le=100)
    batch_max_items: int = Field(100, ge=1, le=1000)

    @field_validator("cors_origins", "ma_api_allowed_hosts", mode="before")
    @classmethod
    def _comma_separated(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @field_validator(
        "rate_limit_login", "rate_limit_login_account", "rate_limit_scoring", "rate_limit_upload"
    )
    @classmethod
    def _rate_limit(cls, value: str) -> str:
        value = value.strip()
        if value:
            parse_limit(value)  # raises ValueError, reported as a settings error
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
