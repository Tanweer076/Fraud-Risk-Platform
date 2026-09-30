from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionBatch(Base):
    """One load of a month's GL, MA and FA records plus its join map."""

    __tablename__ = "ingestion_batches"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="status"),
        CheckConstraint("method IN ('file', 'api', 'cli')", name="method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(6), index=True)
    method: Mapped[str] = mapped_column(String(8))  # how MA arrived: file upload, REST API, CLI
    status: Mapped[str] = mapped_column(String(12), default="queued")
    files: Mapped[dict] = mapped_column(JSONB, default=dict)  # source -> file name or URL
    records: Mapped[dict] = mapped_column(JSONB, default=dict)  # source -> rows read
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # suspicious counts by break type
    transactions_loaded: Mapped[int] = mapped_column(default=0)
    transactions_scored: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None]
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountKeyMap(Base):
    """The join map of a month: GL account -> MA customer key and FA key, effective-dated."""

    __tablename__ = "account_key_map"
    __table_args__ = (Index(None, "period", "gl_account_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(6))
    gl_account_id: Mapped[str] = mapped_column(Text)
    ma_customer_key: Mapped[str] = mapped_column(Text)
    fa_key: Mapped[str] = mapped_column(Text)
    entity: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date]
    effective_to: Mapped[date]
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_batches.id", ondelete="SET NULL")
    )
