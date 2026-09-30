from datetime import date, datetime

from app.schemas.common import ORMModel
from app.schemas.predictions import PredictionOut
from app.schemas.reviews import ReviewOut


class SystemRecordOut(ORMModel):
    account_key: str | None
    transaction_date: date | None
    amount: float | None
    currency: str | None
    country: str | None
    description: str | None
    rule_violations: list[str] | None


class TransactionSummary(ORMModel):
    transaction_id: str
    period: str
    gl_account_id: str | None
    transaction_date: date | None
    amount: float | None
    currency: str | None
    country: str | None
    description: str | None
    in_gl: bool
    in_ma: bool
    in_fa: bool
    break_types: list[str]
    is_suspicious: bool
    risk_score: int | None
    risk_band: str | None
    priority: int | None
    exposure_usd: float | None
    model_version: str | None
    scored_at: datetime | None
    review_outcome: str | None
    source: str


class TransactionDetail(TransactionSummary):
    systems: dict[str, SystemRecordOut | None]
    expected_ma_key: str | None
    expected_fa_key: str | None
    gl_account_mapped: bool
    predictions: list[PredictionOut]
    reviews: list[ReviewOut]
