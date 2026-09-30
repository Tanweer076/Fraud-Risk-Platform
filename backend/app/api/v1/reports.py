import csv
import io
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.api.v1.transactions import Filters
from app.models import Transaction
from app.repositories import transactions as repo

router = APIRouter(prefix="/reports", tags=["reports"])

COLUMNS = [
    "transaction_id",
    "period",
    "gl_account_id",
    "transaction_date",
    "amount",
    "currency",
    "country",
    "description",
    "in_gl",
    "in_ma",
    "in_fa",
    "amount_gl",
    "amount_ma",
    "amount_fa",
    "break_types",
    "risk_score",
    "risk_band",
    "priority",
    "exposure_usd",
    "model_version",
    "review_outcome",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(value)
    text = str(value)
    # Keep spreadsheet apps from running cell content as a formula.
    return "'" + text if text[:1] in ("=", "+", "-", "@") and not _is_number(text) else text


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


@router.get("/export")
def export(request: Request, _: CurrentUser, filters: Filters, format: Literal["csv"] = "csv"):
    """Download transactions matching the same filters as GET /transactions, as CSV."""
    stmt = repo.order_by(repo.apply_filters(select(Transaction), filters), repo.DEFAULT_SORT)
    make_session = request.app.state.sessionmaker

    def rows() -> Iterator[str]:
        # Its own session: the response streams after the request's session has closed.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(COLUMNS)
        with make_session() as db:
            for tx in db.scalars(stmt.execution_options(yield_per=2000)):
                writer.writerow([_cell(getattr(tx, c)) for c in COLUMNS])
                if buffer.tell() > 64_000:
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate()
        yield buffer.getvalue()

    name = f"transactions_{filters.period or 'all'}.csv"
    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
