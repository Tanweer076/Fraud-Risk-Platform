from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.model_version import ModelVersion

Money = Numeric(18, 2, asdecimal=False)
NullableJSON = JSONB(none_as_null=True)


class Transaction(Base):
    """One TransactionID linked across GL, MA and FA, with its break labels and latest score.

    Text columns are unbounded on purpose: malformed source values must load so the rule checks
    can flag them.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("source IN ('batch', 'api')", name="source"),
        CheckConstraint(
            "review_outcome IS NULL OR review_outcome IN ('confirmed', 'false_positive')",
            name="review_outcome",
        ),
        Index(None, "gl_account_id", "transaction_date"),
        Index(None, "period", "is_suspicious"),
        Index(None, "risk_band"),
        Index(None, "priority"),
        Index(None, "break_types", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(Text, unique=True)
    period: Mapped[str] = mapped_column(String(6))
    source: Mapped[str] = mapped_column(String(8))
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_batches.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # Linked view: the GL value, else MA, else FA. Used for filters, charts and history.
    gl_account_id: Mapped[str | None] = mapped_column(Text)
    transaction_date: Mapped[date | None]
    amount: Mapped[float | None] = mapped_column(Money)
    currency: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    # Each system's own record (all NULL when the system has none).
    in_gl: Mapped[bool]
    in_ma: Mapped[bool]
    in_fa: Mapped[bool]
    account_key_gl: Mapped[str | None] = mapped_column(Text)
    account_key_ma: Mapped[str | None] = mapped_column(Text)
    account_key_fa: Mapped[str | None] = mapped_column(Text)
    transaction_date_gl: Mapped[date | None]
    transaction_date_ma: Mapped[date | None]
    transaction_date_fa: Mapped[date | None]
    amount_gl: Mapped[float | None] = mapped_column(Money)
    amount_ma: Mapped[float | None] = mapped_column(Money)
    amount_fa: Mapped[float | None] = mapped_column(Money)
    currency_gl: Mapped[str | None] = mapped_column(Text)
    currency_ma: Mapped[str | None] = mapped_column(Text)
    currency_fa: Mapped[str | None] = mapped_column(Text)
    country_gl: Mapped[str | None] = mapped_column(Text)
    country_ma: Mapped[str | None] = mapped_column(Text)
    country_fa: Mapped[str | None] = mapped_column(Text)
    description_gl: Mapped[str | None] = mapped_column(Text)
    description_ma: Mapped[str | None] = mapped_column(Text)
    description_fa: Mapped[str | None] = mapped_column(Text)
    rule_violations_gl: Mapped[list | None] = mapped_column(NullableJSON)
    rule_violations_ma: Mapped[list | None] = mapped_column(NullableJSON)
    rule_violations_fa: Mapped[list | None] = mapped_column(NullableJSON)

    # Join-map resolution for the GL account.
    expected_ma_key: Mapped[str | None] = mapped_column(Text)
    expected_fa_key: Mapped[str | None] = mapped_column(Text)
    gl_account_mapped: Mapped[bool]

    # Break labels (the training target) derived from the linked records.
    break_types: Mapped[list] = mapped_column(JSONB, default=list)
    is_suspicious: Mapped[bool]

    # Latest score, copied from the newest prediction for list views and the review queue.
    risk_score: Mapped[int | None] = mapped_column(SmallInteger)
    risk_band: Mapped[str | None] = mapped_column(String(10))
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    exposure_usd: Mapped[float | None] = mapped_column(Money)
    probability: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(32))
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set when a reviewer's decision is approved (maker-checker).
    review_outcome: Mapped[str | None] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Prediction(Base):
    """One scoring of a transaction by one model version. History is kept."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("source IN ('batch', 'api')", name="source"),
        Index(None, "transaction_pk", "created_at"),
        Index(None, "risk_band", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_pk: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    probability: Mapped[float] = mapped_column(Float)
    model_score: Mapped[int] = mapped_column(SmallInteger)
    risk_score: Mapped[int] = mapped_column(SmallInteger)
    risk_band: Mapped[str] = mapped_column(String(10))
    priority: Mapped[int] = mapped_column(SmallInteger)
    exposure_usd: Mapped[float] = mapped_column(Money)
    break_types: Mapped[list] = mapped_column(JSONB)
    rule_hits: Mapped[list] = mapped_column(JSONB)
    top_factors: Mapped[list] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(8))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transaction: Mapped[Transaction] = relationship(lazy="joined")
    model: Mapped[ModelVersion] = relationship(lazy="joined")

    @property
    def transaction_id(self) -> str:
        return self.transaction.transaction_id

    @property
    def model_version(self) -> str:
        return self.model.version
