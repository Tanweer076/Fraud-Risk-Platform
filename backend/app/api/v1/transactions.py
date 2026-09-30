from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.ml.frames import SYSTEM_FIELDS
from app.models import Transaction
from app.repositories import transactions as repo
from app.schemas.common import Band, Page
from app.schemas.transactions import SystemRecordOut, TransactionDetail, TransactionSummary

router = APIRouter(prefix="/transactions", tags=["transactions"])


def transaction_filters(
    period: Annotated[str | None, Query(pattern=r"^\d{6}$")] = None,
    band: Annotated[list[Band] | None, Query()] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    break_type: str | None = None,
    suspicious: bool | None = None,
    currency: str | None = None,
    country: str | None = None,
    account: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: Annotated[str | None, Query(max_length=64)] = None,
    reviewed: bool | None = None,
) -> repo.TransactionFilters:
    return repo.TransactionFilters(
        period=period,
        band=band,
        min_score=min_score,
        max_score=max_score,
        break_type=break_type,
        suspicious=suspicious,
        currency=currency,
        country=country,
        account=account,
        date_from=date_from,
        date_to=date_to,
        search=search,
        reviewed=reviewed,
    )


Filters = Annotated[repo.TransactionFilters, Depends(transaction_filters)]


@router.get("", response_model=Page[TransactionSummary])
def list_transactions(
    db: DB,
    _: CurrentUser,
    filters: Filters,
    sort: str = "-priority,-risk_score",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """Stored transactions with their latest score. `sort` takes comma-separated fields
    (priority, risk_score, transaction_date, amount, exposure_usd, scored_at, transaction_id),
    each optionally prefixed with '-' for descending order."""
    stmt = repo.order_by(repo.apply_filters(select(Transaction), filters), sort)
    items, total = repo.page(db, stmt, page, page_size)
    return Page[TransactionSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/{transaction_id}", response_model=TransactionDetail)
def get_transaction(transaction_id: str, db: DB, _: CurrentUser):
    """GL, MA and FA records side by side, with prediction history and reviews."""
    tx = repo.get_or_404(db, transaction_id)
    systems = {
        s: (
            SystemRecordOut(**{f: getattr(tx, f"{f}_{s}") for f in SYSTEM_FIELDS})
            if getattr(tx, f"in_{s}")
            else None
        )
        for s in ("gl", "ma", "fa")
    }
    return TransactionDetail(
        **TransactionSummary.model_validate(tx).model_dump(),
        systems=systems,
        expected_ma_key=tx.expected_ma_key,
        expected_fa_key=tx.expected_fa_key,
        gl_account_mapped=tx.gl_account_mapped,
        predictions=repo.predictions_of(db, tx),
        reviews=repo.reviews_of(db, tx),
    )
