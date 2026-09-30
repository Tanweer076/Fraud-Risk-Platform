from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import DB, AppSettings, Checker, CurrentUser, Maker
from app.repositories import transactions as repo
from app.schemas.common import Page
from app.schemas.reviews import (
    ApproveRequest,
    BulkApproveRequest,
    BulkApproveResult,
    RejectRequest,
    ReviewCreate,
    ReviewOut,
)
from app.schemas.transactions import TransactionSummary
from app.services import reviews

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/queue", response_model=Page[TransactionSummary])
def queue(
    db: DB,
    settings: AppSettings,
    _: CurrentUser,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """Flagged transactions nobody has reviewed yet, highest priority first."""
    stmt = reviews.queue_query(settings.review_min_score if min_score is None else min_score)
    items, total = repo.page(db, stmt, page, page_size)
    return Page[TransactionSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("", response_model=Page[ReviewOut])
def list_reviews(
    db: DB,
    _: CurrentUser,
    status: Literal["pending", "approved", "rejected"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """Reviews; pending ones come highest priority first."""
    items, total = reviews.list_reviews(db, status, page, page_size)
    return Page[ReviewOut](items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewCreate, db: DB, user: Maker):
    """Record a decision on a transaction; it waits for an approver."""
    return reviews.create(db, data, user)


@router.post("/{review_id}/approve", response_model=ReviewOut)
def approve(review_id: int, data: ApproveRequest, db: DB, user: Checker):
    return reviews.approve(db, review_id, user, data.note)


@router.post("/{review_id}/reject", response_model=ReviewOut)
def reject(review_id: int, data: RejectRequest, db: DB, user: Checker):
    return reviews.reject(db, review_id, user, data.note)


@router.post("/bulk-approve", response_model=BulkApproveResult)
def bulk_approve(data: BulkApproveRequest, db: DB, user: Checker):
    """Approve many reviews at once; ones that cannot be approved are listed with the reason."""
    return reviews.bulk_approve(db, data.review_ids, user, data.note)
