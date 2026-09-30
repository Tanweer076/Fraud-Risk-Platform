from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.transaction import Transaction
from app.models.user import User


class Review(Base):
    """Maker-checker: an analyst records a decision, a different user approves or rejects it."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('confirmed', 'false_positive')", name="decision"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="status"),
        # A transaction has at most one review that is pending or approved.
        Index(
            "uq_reviews_one_open_per_transaction",
            "transaction_pk",
            unique=True,
            postgresql_where=text("status IN ('pending', 'approved')"),
        ),
        Index(None, "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_pk: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL")
    )
    analyst_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approver_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transaction: Mapped[Transaction] = relationship(lazy="joined")
    analyst: Mapped[User] = relationship(foreign_keys=[analyst_id], lazy="joined")
    approver: Mapped[User | None] = relationship(foreign_keys=[approver_id], lazy="joined")

    @property
    def transaction_id(self) -> str:
        return self.transaction.transaction_id

    @property
    def analyst_email(self) -> str:
        return self.analyst.email

    @property
    def approver_email(self) -> str | None:
        return self.approver.email if self.approver else None
