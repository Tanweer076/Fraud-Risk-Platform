"""Maker-checker review of flagged transactions.

An analyst (the maker) records a decision on a flagged transaction: confirmed or false
positive. A different user with the approver role (the checker) approves or rejects it. An
approved decision is written onto the transaction as its review outcome; a rejected one sends
the transaction back to the queue.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.models import Review, Transaction, User
from app.repositories import transactions as repo
from app.schemas.reviews import BulkApproveResult, ReviewCreate, SkippedReview
from app.services import audit

OPEN_STATUSES = ("pending", "approved")


def _has_open_review():
    return (
        select(Review.id)
        .where(Review.transaction_pk == Transaction.id, Review.status.in_(OPEN_STATUSES))
        .exists()
    )


def queue_query(min_score: int):
    """Transactions at or above min_score that nobody has reviewed yet, most urgent first."""
    return (
        select(Transaction)
        .where(Transaction.risk_score >= min_score, ~_has_open_review())
        .order_by(
            Transaction.priority.desc().nulls_last(),
            Transaction.risk_score.desc(),
            Transaction.id,
        )
    )


def queue_size(db: Session, min_score: int, period: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.risk_score >= min_score, ~_has_open_review())
    )
    if period:
        stmt = stmt.where(Transaction.period == period)
    return db.scalar(stmt) or 0


def list_reviews(db: Session, status: str | None, page: int, page_size: int):
    stmt = select(Review).join(Transaction, Review.transaction_pk == Transaction.id)
    if status:
        stmt = stmt.where(Review.status == status)
    if status == "pending":
        stmt = stmt.order_by(Transaction.priority.desc().nulls_last(), Review.created_at)
    else:
        stmt = stmt.order_by(Review.created_at.desc(), Review.id.desc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return list(items), total


def _get_for_update(db: Session, review_id: int) -> Review:
    review = db.scalar(select(Review).where(Review.id == review_id).with_for_update(of=Review))
    if review is None:
        raise NotFound(f"Review {review_id} not found")
    return review


def create(db: Session, data: ReviewCreate, analyst: User) -> Review:
    tx = repo.get(db, data.transaction_id, for_update=True)
    if tx is None:
        raise NotFound(f"Transaction {data.transaction_id} not found")
    prediction = repo.latest_prediction(db, tx)
    if prediction is None:
        raise Conflict(f"Transaction {data.transaction_id} has not been scored yet")
    review = Review(
        transaction_pk=tx.id,
        prediction_id=prediction.id,
        analyst_id=analyst.id,
        decision=data.decision,
        note=data.note,
        status="pending",
    )
    db.add(review)
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict(
            f"Transaction {data.transaction_id} already has a pending or approved review"
        ) from exc
    audit.record(
        db,
        analyst,
        "review.create",
        "review",
        review.id,
        after={"transaction_id": tx.transaction_id, "decision": data.decision, "note": data.note},
    )
    db.commit()
    db.refresh(review)
    return review


def _check_can_decide(review: Review, approver: User) -> None:
    if review.status != "pending":
        raise Conflict(f"Review {review.id} is already {review.status}")
    if review.analyst_id == approver.id:
        raise Forbidden("Maker-checker: you cannot approve or reject your own review")


def _decide(db: Session, review: Review, approver: User, status: str, note: str) -> None:
    review.status = status
    review.approver_id = approver.id
    review.approver_note = note
    review.decided_at = datetime.now(UTC)
    if status == "approved":
        review.transaction.review_outcome = review.decision
    audit.record(
        db,
        approver,
        f"review.{'approve' if status == 'approved' else 'reject'}",
        "review",
        review.id,
        before={"status": "pending"},
        after={"status": status, "note": note, "decision": review.decision},
    )


def approve(db: Session, review_id: int, approver: User, note: str) -> Review:
    return _decide_one(db, review_id, approver, "approved", note)


def reject(db: Session, review_id: int, approver: User, note: str) -> Review:
    return _decide_one(db, review_id, approver, "rejected", note)


def _decide_one(db: Session, review_id: int, approver: User, status: str, note: str) -> Review:
    review = _get_for_update(db, review_id)
    _check_can_decide(review, approver)
    _decide(db, review, approver, status, note)
    db.commit()
    db.refresh(review)
    return review


def bulk_approve(
    db: Session, review_ids: list[int], approver: User, note: str
) -> BulkApproveResult:
    approved, skipped = [], []
    for review_id in dict.fromkeys(review_ids):  # de-duplicate, keep order
        try:
            review = _get_for_update(db, review_id)
            _check_can_decide(review, approver)
        except AppError as exc:
            skipped.append(SkippedReview(id=review_id, reason=exc.detail))
            continue
        _decide(db, review, approver, "approved", note)
        approved.append(review_id)
    db.commit()
    return BulkApproveResult(approved=approved, skipped=skipped)
