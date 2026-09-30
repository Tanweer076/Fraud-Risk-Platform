"""Queries on transactions, their predictions and the join map."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd
from fraudml.ingest.join_map import JOIN_MAP_COLUMNS
from sqlalchemy import Select, Text, any_, bindparam, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.ml.frames import HISTORY_COLUMNS, history_frame, join_map_frame
from app.models import AccountKeyMap, Prediction, Review, Transaction

SORTABLE = {
    "priority": Transaction.priority,
    "risk_score": Transaction.risk_score,
    "transaction_date": Transaction.transaction_date,
    "amount": Transaction.amount,
    "exposure_usd": Transaction.exposure_usd,
    "scored_at": Transaction.scored_at,
    "transaction_id": Transaction.transaction_id,
}


@dataclass
class TransactionFilters:
    period: str | None = None
    band: list[str] | None = None
    min_score: int | None = None
    max_score: int | None = None
    break_type: str | None = None
    suspicious: bool | None = None
    currency: str | None = None
    country: str | None = None
    account: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    search: str | None = None
    reviewed: bool | None = None


def apply_filters(stmt: Select, f: TransactionFilters) -> Select:
    t = Transaction
    conditions = []
    if f.period:
        conditions.append(t.period == f.period)
    if f.band:
        conditions.append(t.risk_band.in_(f.band))
    if f.min_score is not None:
        conditions.append(t.risk_score >= f.min_score)
    if f.max_score is not None:
        conditions.append(t.risk_score <= f.max_score)
    if f.break_type:
        conditions.append(t.break_types.contains([f.break_type]))
    if f.suspicious is not None:
        conditions.append(t.is_suspicious.is_(f.suspicious))
    if f.currency:
        conditions.append(t.currency == f.currency)
    if f.country:
        conditions.append(t.country == f.country)
    if f.account:
        conditions.append(t.gl_account_id == f.account)
    if f.date_from:
        conditions.append(t.transaction_date >= f.date_from)
    if f.date_to:
        conditions.append(t.transaction_date <= f.date_to)
    if f.reviewed is not None:
        reviewed = t.review_outcome.is_not(None)
        conditions.append(reviewed if f.reviewed else ~reviewed)
    if f.search:
        escaped = f.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        conditions.append(
            or_(
                t.transaction_id.ilike(like),
                t.gl_account_id.ilike(like),
                t.description.ilike(like),
            )
        )
    return stmt.where(*conditions)


def order_by(stmt: Select, sort: str) -> Select:
    """`sort` is a comma-separated list of fields, each optionally prefixed with '-'."""
    clauses = []
    for part in [p.strip() for p in sort.split(",") if p.strip()]:
        name = part.lstrip("-")
        if name not in SORTABLE:
            raise BadRequest(f"Cannot sort by {name!r}; use one of {', '.join(SORTABLE)}")
        column = SORTABLE[name]
        clauses.append(column.desc().nulls_last() if part.startswith("-") else column.asc())
    return stmt.order_by(*clauses, Transaction.id)


def page(db: Session, stmt: Select, page: int, page_size: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), int(total or 0)


def get(db: Session, transaction_id: str, for_update: bool = False) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_or_404(db: Session, transaction_id: str) -> Transaction:
    tx = get(db, transaction_id)
    if tx is None:
        raise NotFound(f"Transaction {transaction_id} not found")
    return tx


def predictions_of(db: Session, tx: Transaction) -> list[Prediction]:
    stmt = (
        select(Prediction)
        .where(Prediction.transaction_pk == tx.id)
        .order_by(Prediction.created_at.desc(), Prediction.id.desc())
    )
    return list(db.scalars(stmt).unique())


def latest_prediction(db: Session, tx: Transaction) -> Prediction | None:
    stmt = (
        select(Prediction)
        .where(Prediction.transaction_pk == tx.id)
        .order_by(Prediction.created_at.desc(), Prediction.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).unique().first()


def reviews_of(db: Session, tx: Transaction) -> list[Review]:
    stmt = select(Review).where(Review.transaction_pk == tx.id).order_by(Review.created_at.desc())
    return list(db.scalars(stmt).unique())


def join_map_for(db: Session, period: str, gl_account: str | None) -> pd.DataFrame:
    """The account's join-map rows for `period`.

    Falls back to the latest earlier period that has a join map, then to the earliest later
    one, so a transaction can be scored before its month's join map is loaded.
    """
    columns = [getattr(AccountKeyMap, c) for c in JOIN_MAP_COLUMNS]
    if not gl_account:
        return join_map_frame([])
    periods = db.scalars(select(AccountKeyMap.period).distinct()).all()
    earlier = [p for p in periods if p <= period]
    chosen = max(earlier) if earlier else min(periods, default=None)
    if chosen is None:
        return join_map_frame([])
    rows = db.execute(
        select(*columns).where(
            AccountKeyMap.period == chosen, AccountKeyMap.gl_account_id == gl_account
        )
    ).all()
    return join_map_frame(rows)


def _history_columns():
    return [getattr(Transaction, c) for c in HISTORY_COLUMNS]


def account_history(db: Session, gl_account: str | None, exclude: str) -> pd.DataFrame | None:
    """The account's other stored transactions, for behavioural features."""
    if not gl_account:
        return None
    rows = db.execute(
        select(*_history_columns()).where(
            Transaction.gl_account_id == gl_account, Transaction.transaction_id != exclude
        )
    ).all()
    return history_frame(rows)


def period_history(db: Session, before: str, accounts: Sequence[str]) -> pd.DataFrame | None:
    """Stored transactions of these accounts from months before `before`."""
    if len(accounts) == 0:
        return None
    param = bindparam("accounts", value=list(accounts), type_=ARRAY(Text))
    rows = db.execute(
        select(*_history_columns()).where(
            Transaction.period < before, Transaction.gl_account_id == any_(param)
        )
    ).all()
    return history_frame(rows)
