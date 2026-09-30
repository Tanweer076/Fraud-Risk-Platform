from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DB, AppSettings, CurrentUser, Maker, Registry, Rules
from app.core.errors import NotFound
from app.models import Prediction
from app.schemas.predictions import (
    BatchPredictionRequest,
    BatchPredictionResult,
    PredictionOut,
    PredictionRequest,
    ScoreResult,
)
from app.services import scoring

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", response_model=ScoreResult, status_code=status.HTTP_201_CREATED)
def score_transaction(
    req: PredictionRequest, db: DB, registry: Registry, rules: Rules, user: Maker
):
    """Score one transaction and store it with its risk assessment.

    Send one system's record, plus the other systems' records of the same transaction when
    known. Records for a TransactionID that is already stored are added to it (409 if that
    system's record is already there) and the transaction is re-scored.
    """
    return scoring.score_submission(db, registry, rules, req, user)


@router.post("/batch", response_model=BatchPredictionResult)
def score_batch(
    body: BatchPredictionRequest,
    db: DB,
    registry: Registry,
    rules: Rules,
    settings: AppSettings,
    user: Maker,
):
    """Score several transactions; each succeeds or fails on its own."""
    return scoring.score_batch(db, registry, rules, settings, body.transactions, user)


@router.get("/{prediction_id}", response_model=PredictionOut)
def get_prediction(prediction_id: int, db: DB, _: CurrentUser):
    prediction = db.scalars(select(Prediction).where(Prediction.id == prediction_id)).first()
    if prediction is None:
        raise NotFound(f"Prediction {prediction_id} not found")
    return prediction
