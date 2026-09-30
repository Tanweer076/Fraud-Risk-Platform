from datetime import datetime

from app.schemas.common import ORMModel


class BatchOut(ORMModel):
    id: int
    period: str
    method: str
    status: str
    files: dict
    records: dict
    summary: dict
    transactions_loaded: int
    transactions_scored: int
    error: str | None
    duration_ms: int | None
    created_by_id: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
