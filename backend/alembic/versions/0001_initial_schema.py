"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("train_periods", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("test_period", sa.String(length=6), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_model_versions_version")),
    )
    op.create_index(
        "uq_model_versions_one_active",
        "model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('analyst', 'approver', 'admin')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "before", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "after", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_audit_log_entity_entity_id"), "audit_log", ["entity", "entity_id"], unique=False
    )
    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("records", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("transactions_loaded", sa.Integer(), nullable=False),
        sa.Column("transactions_scored", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "method IN ('file', 'api', 'cli')", name=op.f("ck_ingestion_batches_method")
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name=op.f("ck_ingestion_batches_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_ingestion_batches_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_batches")),
    )
    op.create_index(
        op.f("ix_ingestion_batches_period"), "ingestion_batches", ["period"], unique=False
    )
    op.create_table(
        "account_key_map",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("gl_account_id", sa.Text(), nullable=False),
        sa.Column("ma_customer_key", sa.Text(), nullable=False),
        sa.Column("fa_key", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["ingestion_batches.id"],
            name=op.f("fk_account_key_map_batch_id_ingestion_batches"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_key_map")),
    )
    op.create_index(
        op.f("ix_account_key_map_period_gl_account_id"),
        "account_key_map",
        ["period", "gl_account_id"],
        unique=False,
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("gl_account_id", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("in_gl", sa.Boolean(), nullable=False),
        sa.Column("in_ma", sa.Boolean(), nullable=False),
        sa.Column("in_fa", sa.Boolean(), nullable=False),
        sa.Column("account_key_gl", sa.Text(), nullable=True),
        sa.Column("account_key_ma", sa.Text(), nullable=True),
        sa.Column("account_key_fa", sa.Text(), nullable=True),
        sa.Column("transaction_date_gl", sa.Date(), nullable=True),
        sa.Column("transaction_date_ma", sa.Date(), nullable=True),
        sa.Column("transaction_date_fa", sa.Date(), nullable=True),
        sa.Column("amount_gl", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=True),
        sa.Column("amount_ma", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=True),
        sa.Column("amount_fa", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=True),
        sa.Column("currency_gl", sa.Text(), nullable=True),
        sa.Column("currency_ma", sa.Text(), nullable=True),
        sa.Column("currency_fa", sa.Text(), nullable=True),
        sa.Column("country_gl", sa.Text(), nullable=True),
        sa.Column("country_ma", sa.Text(), nullable=True),
        sa.Column("country_fa", sa.Text(), nullable=True),
        sa.Column("description_gl", sa.Text(), nullable=True),
        sa.Column("description_ma", sa.Text(), nullable=True),
        sa.Column("description_fa", sa.Text(), nullable=True),
        sa.Column(
            "rule_violations_gl",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "rule_violations_ma",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "rule_violations_fa",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("expected_ma_key", sa.Text(), nullable=True),
        sa.Column("expected_fa_key", sa.Text(), nullable=True),
        sa.Column("gl_account_mapped", sa.Boolean(), nullable=False),
        sa.Column("break_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False),
        sa.Column("risk_score", sa.SmallInteger(), nullable=True),
        sa.Column("risk_band", sa.String(length=10), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=True),
        sa.Column(
            "exposure_usd", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=True
        ),
        sa.Column("probability", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=32), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_outcome", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_outcome IS NULL OR review_outcome IN ('confirmed', 'false_positive')",
            name=op.f("ck_transactions_review_outcome"),
        ),
        sa.CheckConstraint("source IN ('batch', 'api')", name=op.f("ck_transactions_source")),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["ingestion_batches.id"],
            name=op.f("fk_transactions_batch_id_ingestion_batches"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_transactions_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("transaction_id", name=op.f("uq_transactions_transaction_id")),
    )
    op.create_index(
        op.f("ix_transactions_break_types"),
        "transactions",
        ["break_types"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_transactions_gl_account_id_transaction_date"),
        "transactions",
        ["gl_account_id", "transaction_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_period_is_suspicious"),
        "transactions",
        ["period", "is_suspicious"],
        unique=False,
    )
    op.create_index(op.f("ix_transactions_priority"), "transactions", ["priority"], unique=False)
    op.create_index(op.f("ix_transactions_risk_band"), "transactions", ["risk_band"], unique=False)
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_pk", sa.BigInteger(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("model_score", sa.SmallInteger(), nullable=False),
        sa.Column("risk_score", sa.SmallInteger(), nullable=False),
        sa.Column("risk_band", sa.String(length=10), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column(
            "exposure_usd", sa.Numeric(precision=18, scale=2, asdecimal=False), nullable=False
        ),
        sa.Column("break_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_hits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('batch', 'api')", name=op.f("ck_predictions_source")),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_predictions_model_version_id_model_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_pk"],
            ["transactions.id"],
            name=op.f("fk_predictions_transaction_pk_transactions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictions")),
    )
    op.create_index(
        op.f("ix_predictions_risk_band_created_at"),
        "predictions",
        ["risk_band", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predictions_transaction_pk_created_at"),
        "predictions",
        ["transaction_pk", "created_at"],
        unique=False,
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_pk", sa.BigInteger(), nullable=False),
        sa.Column("prediction_id", sa.BigInteger(), nullable=True),
        sa.Column("analyst_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("approver_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'false_positive')", name=op.f("ck_reviews_decision")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name=op.f("ck_reviews_status")
        ),
        sa.ForeignKeyConstraint(
            ["analyst_id"], ["users.id"], name=op.f("fk_reviews_analyst_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["users.id"], name=op.f("fk_reviews_approver_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["predictions.id"],
            name=op.f("fk_reviews_prediction_id_predictions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_pk"],
            ["transactions.id"],
            name=op.f("fk_reviews_transaction_pk_transactions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
    )
    op.create_index(
        op.f("ix_reviews_status_created_at"), "reviews", ["status", "created_at"], unique=False
    )
    op.create_index(
        "uq_reviews_one_open_per_transaction",
        "reviews",
        ["transaction_pk"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_reviews_one_open_per_transaction",
        table_name="reviews",
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )
    op.drop_index(op.f("ix_reviews_status_created_at"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(op.f("ix_predictions_transaction_pk_created_at"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_risk_band_created_at"), table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(op.f("ix_transactions_risk_band"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_priority"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_period_is_suspicious"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_gl_account_id_transaction_date"), table_name="transactions")
    op.drop_index(
        op.f("ix_transactions_break_types"), table_name="transactions", postgresql_using="gin"
    )
    op.drop_table("transactions")
    op.drop_index(op.f("ix_account_key_map_period_gl_account_id"), table_name="account_key_map")
    op.drop_table("account_key_map")
    op.drop_index(op.f("ix_ingestion_batches_period"), table_name="ingestion_batches")
    op.drop_table("ingestion_batches")
    op.drop_index(op.f("ix_audit_log_entity_entity_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_index(
        "uq_model_versions_one_active",
        table_name="model_versions",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("model_versions")
