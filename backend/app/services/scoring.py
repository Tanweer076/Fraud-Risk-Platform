"""Score transactions submitted through the API and store them with their predictions.

A submission is one system's record of a transaction, optionally with the other systems'
records of it. If the TransactionID is already stored, the new records are added to it and the
whole transaction is re-linked and re-scored; resubmitting a system it already has is a conflict.
"""

import secrets
import time
from datetime import UTC, datetime

from fraudml.canonical.schema import SYSTEMS
from fraudml.ingest.rules import Rule
from fraudml.pipeline import label_records
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import Settings
from app.core.errors import AppError, BadRequest, Conflict
from app.ml.frames import canonical_frames, stored_record, transaction_values
from app.ml.registry import LoadedModel, ModelRegistry
from app.models import Prediction, Transaction, User
from app.repositories import transactions as repo
from app.schemas.predictions import (
    BatchItem,
    BatchPredictionResult,
    PredictionOut,
    PredictionRequest,
    ScoreResult,
)
from app.services import audit


def new_transaction_id() -> str:
    return secrets.token_hex(8).upper()


def score_fields(scored, model: LoadedModel, scored_at: datetime) -> dict:
    """The latest-score columns copied onto the transaction."""
    return {
        "risk_score": int(scored["risk_score"]),
        "risk_band": str(scored["band"]),
        "priority": int(scored["priority"]),
        "exposure_usd": float(scored["exposure_usd"]),
        "probability": float(scored["probability"]),
        "model_version": model.version,
        "scored_at": scored_at,
    }


def prediction_values(scored, model: LoadedModel, source: str) -> dict:
    return {
        "model_version_id": model.id,
        "probability": float(scored["probability"]),
        "model_score": int(scored["model_score"]),
        "risk_score": int(scored["risk_score"]),
        "risk_band": str(scored["band"]),
        "priority": int(scored["priority"]),
        "exposure_usd": float(scored["exposure_usd"]),
        "break_types": list(scored["break_types"]),
        "rule_hits": list(scored["rule_hits"]),
        "top_factors": list(scored["top_factors"]),
        "source": source,
    }


def score_submission(
    db: Session,
    registry: ModelRegistry,
    rules: list[Rule],
    req: PredictionRequest,
    user: User,
    commit: bool = True,
) -> ScoreResult:
    started = time.perf_counter()
    model = registry.current(db)
    transaction_id = req.transaction_id or new_transaction_id()
    submitted = req.records()

    tx = repo.get(db, transaction_id, for_update=True)
    if tx is None:
        records = submitted
        first = submitted.get("gl") or submitted[req.source_system]
        period = first["transaction_date"].strftime("%Y%m")
    else:
        clash = [s.upper() for s in SYSTEMS if s in submitted and getattr(tx, f"in_{s}")]
        if clash:
            raise Conflict(f"Transaction {transaction_id} already has a {'/'.join(clash)} record")
        records = {s: stored_record(tx, s) for s in SYSTEMS} | submitted
        period = tx.period

    frames = canonical_frames(transaction_id, records)
    gl = frames["gl"]
    gl_account = gl["account_key"].iloc[0] if len(gl) else None
    join_map = repo.join_map_for(db, period, gl_account)
    labelled = label_records(frames, join_map, rules, period)
    labelled["period"] = period
    history = repo.account_history(db, gl_account, exclude=transaction_id)
    scored = model.scorer.score(labelled, history=history, explain_min_score=0).iloc[0]

    values = transaction_values(labelled.iloc[0]) | score_fields(scored, model, datetime.now(UTC))
    created = tx is None
    if created:
        tx = Transaction(**values, period=period, source="api", created_by_id=user.id)
        db.add(tx)
    else:
        for key, value in values.items():
            setattr(tx, key, value)
    try:
        db.flush()
    except IntegrityError as exc:  # the same new TransactionID stored concurrently
        raise Conflict(f"Transaction {transaction_id} was stored by another request") from exc

    elapsed = time.perf_counter() - started
    prediction = Prediction(
        transaction_pk=tx.id,
        **prediction_values(scored, model, source="api"),
        latency_ms=round(elapsed * 1000, 1),
    )
    db.add(prediction)
    db.flush()
    metrics.SCORING_LATENCY.observe(elapsed)
    metrics.record_scores("api", {prediction.risk_band: 1}, [prediction.risk_score])
    audit.record(
        db,
        user,
        "prediction.create",
        "transaction",
        transaction_id,
        after={
            "systems": sorted(submitted),
            "risk_score": prediction.risk_score,
            "risk_band": prediction.risk_band,
            "model_version": model.version,
        },
    )
    if commit:
        db.commit()
    db.refresh(prediction)
    return ScoreResult(
        **PredictionOut.model_validate(prediction).model_dump(),
        created=created,
        in_systems=[s for s in SYSTEMS if getattr(tx, f"in_{s}")],
    )


def score_batch(
    db: Session,
    registry: ModelRegistry,
    rules: list[Rule],
    settings: Settings,
    requests: list[PredictionRequest],
    user: User,
) -> BatchPredictionResult:
    """Score each submission on its own savepoint, so one failure does not undo the others."""
    if len(requests) > settings.batch_max_items:
        raise BadRequest(f"At most {settings.batch_max_items} transactions per batch")
    registry.current(db)  # fail fast when no model is active
    items = []
    for i, req in enumerate(requests):
        try:
            with db.begin_nested():
                result = score_submission(db, registry, rules, req, user, commit=False)
            items.append(
                BatchItem(
                    index=i, status="scored", transaction_id=result.transaction_id, result=result
                )
            )
        except AppError as exc:
            items.append(
                BatchItem(
                    index=i,
                    status="error",
                    transaction_id=req.transaction_id,
                    error=exc.detail,
                    status_code=exc.status_code,
                )
            )
    db.commit()
    scored = sum(1 for item in items if item.status == "scored")
    return BatchPredictionResult(scored=scored, failed=len(items) - scored, items=items)
