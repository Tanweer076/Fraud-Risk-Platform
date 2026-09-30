from typing import Literal

from pydantic import BaseModel

BreakdownBy = Literal["currency", "country", "description", "period", "band", "break_type"]


class Summary(BaseModel):
    period: str | None
    periods: list[str]
    transactions: int
    suspicious: int
    suspicious_rate: float
    scored: int
    avg_risk_score: float | None
    high_or_critical: int
    exposure_usd_at_risk: float
    by_band: dict[str, int]
    review_queue: int
    pending_approval: int
    confirmed: int
    false_positive: int


class ScoreBin(BaseModel):
    score_from: int
    score_to: int
    count: int


class BandCount(BaseModel):
    band: str
    count: int
    share: float


class RiskDistribution(BaseModel):
    period: str | None
    bins: list[ScoreBin]
    bands: list[BandCount]


class TrendPoint(BaseModel):
    bucket: str
    transactions: int
    suspicious: int
    suspicious_rate: float
    avg_risk_score: float | None
    high_or_critical: int


class BreakdownRow(BaseModel):
    key: str | None
    transactions: int
    suspicious: int
    suspicious_rate: float
    avg_risk_score: float | None
    high_or_critical: int
    exposure_usd: float


class TopAccount(BaseModel):
    account: str
    transactions: int
    suspicious: int
    max_risk_score: int | None
    exposure_usd: float
    last_transaction_date: str | None
