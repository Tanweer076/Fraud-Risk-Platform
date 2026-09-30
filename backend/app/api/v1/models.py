from fastapi import APIRouter

from app.api.deps import DB, Admin, CurrentUser, Registry
from app.schemas.models import ModelEvaluation, ModelVersionOut
from app.services import models

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelVersionOut])
def list_models(db: DB, _: CurrentUser):
    return models.list_versions(db)


@router.get("/active", response_model=ModelVersionOut)
def active_model(db: DB, _: CurrentUser):
    return models.active(db)


@router.get("/{version_id}/evaluation", response_model=ModelEvaluation)
def evaluation(version_id: int, db: DB, _: CurrentUser):
    """Model comparison, champion metrics, curves, confusion matrices and feature importance."""
    return models.evaluation(db, version_id)


@router.post("/{version_id}/activate", response_model=ModelVersionOut)
def activate(version_id: int, db: DB, registry: Registry, admin: Admin):
    """Make this version the one that scores new transactions. Takes effect at once."""
    return models.activate(db, registry, version_id, admin)


@router.post("/sync", response_model=list[ModelVersionOut])
def sync(db: DB, registry: Registry, admin: Admin):
    """Register artifacts added to MODEL_DIR since startup (e.g. after `fraudml train`)."""
    return models.sync(db, registry, admin)
