from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelVersion(Base):
    """A trained model artifact (see fraudml.models.train). At most one is active."""

    __tablename__ = "model_versions"
    __table_args__ = (
        Index(
            "uq_model_versions_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(Text)
    features: Mapped[list] = mapped_column(JSONB)
    threshold: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSONB)  # champion metrics on the test month
    train_periods: Mapped[list] = mapped_column(JSONB)
    test_period: Mapped[str] = mapped_column(String(6))
    details: Mapped[dict] = mapped_column(JSONB)  # full metadata.json: comparison, evaluation
    is_active: Mapped[bool] = mapped_column(default=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
