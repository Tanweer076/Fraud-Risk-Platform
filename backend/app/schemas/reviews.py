from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import Decision, ORMModel


class ReviewCreate(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=64)
    decision: Decision
    note: str = Field("", max_length=2000)


class ApproveRequest(BaseModel):
    note: str = Field("", max_length=2000)


class RejectRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000, description="Why the decision is rejected.")


class BulkApproveRequest(BaseModel):
    review_ids: list[int] = Field(min_length=1, max_length=500)
    note: str = Field("", max_length=2000)


class ReviewOut(ORMModel):
    id: int
    transaction_id: str
    prediction_id: int | None
    decision: Decision
    note: str
    status: str
    analyst_id: int
    analyst_email: str
    approver_id: int | None
    approver_email: str | None
    approver_note: str | None
    decided_at: datetime | None
    created_at: datetime


class SkippedReview(BaseModel):
    id: int
    reason: str


class BulkApproveResult(BaseModel):
    approved: list[int]
    skipped: list[SkippedReview]
