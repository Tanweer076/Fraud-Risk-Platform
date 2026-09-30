from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Band, ORMModel, System


class RecordIn(BaseModel):
    """One system's record of a transaction. Business rules (ID and account formats, supported
    currencies and countries, amount range) are checked by the rule engine and reported as
    rule_violation breaks, not rejected here."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    account_key: str = Field(min_length=1, max_length=64, examples=["ACC0001"])
    transaction_date: date
    amount: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False, examples=[1250.0])
    currency: str = Field(min_length=1, max_length=8, examples=["USD"])
    country: str = Field(min_length=1, max_length=8, examples=["US"])
    description: str = Field(max_length=255, examples=["Vendor payment"])


class PredictionRequest(RecordIn):
    transaction_id: str | None = Field(
        None,
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Generated (16 hex characters) when left out.",
        examples=["9F3A5C7E1B2D4F60"],
    )
    source_system: System = "gl"
    counterparts: dict[System, RecordIn] = Field(
        default_factory=dict,
        description="The same transaction as recorded by the other systems, when known.",
    )

    @model_validator(mode="after")
    def _counterparts_are_other_systems(self):
        if self.source_system in self.counterparts:
            raise ValueError(f"counterparts cannot repeat the source system ({self.source_system})")
        return self

    def records(self) -> dict[str, dict]:
        """Submitted records by system."""
        own = self.model_dump(include=set(RecordIn.model_fields))
        return {
            self.source_system: own,
            **{s: r.model_dump() for s, r in self.counterparts.items()},
        }


class BatchPredictionRequest(BaseModel):
    transactions: list[PredictionRequest] = Field(min_length=1, max_length=1000)


class RuleHit(BaseModel):
    break_type: str
    reason: str


class Factor(BaseModel):
    reason: str
    features: list[str]
    contribution: float


class PredictionOut(ORMModel):
    id: int
    transaction_id: str
    model_version: str
    probability: float
    model_score: int
    risk_score: int
    risk_band: Band
    priority: int
    exposure_usd: float
    break_types: list[str]
    rule_hits: list[RuleHit]
    top_factors: list[Factor]
    source: str
    latency_ms: float | None
    created_at: datetime


class ScoreResult(PredictionOut):
    created: bool = Field(description="False when the record was added to a known transaction.")
    in_systems: list[System]


class BatchItem(BaseModel):
    index: int
    status: Literal["scored", "error"]
    transaction_id: str | None = None
    result: ScoreResult | None = None
    error: str | None = None
    status_code: int | None = None


class BatchPredictionResult(BaseModel):
    scored: int
    failed: int
    items: list[BatchItem]
