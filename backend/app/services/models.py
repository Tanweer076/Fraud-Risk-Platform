from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.ml.registry import ModelRegistry
from app.models import ModelVersion, User
from app.schemas.models import ModelEvaluation
from app.services import audit


def list_versions(db: Session) -> list[ModelVersion]:
    return list(db.scalars(select(ModelVersion).order_by(ModelVersion.id.desc())))


def get(db: Session, version_id: int) -> ModelVersion:
    version = db.get(ModelVersion, version_id)
    if version is None:
        raise NotFound(f"Model version {version_id} not found")
    return version


def active(db: Session) -> ModelVersion:
    version = db.scalar(select(ModelVersion).where(ModelVersion.is_active))
    if version is None:
        raise NotFound("No model is active")
    return version


def evaluation(db: Session, version_id: int) -> ModelEvaluation:
    version = get(db, version_id)
    details = version.details
    return ModelEvaluation(
        id=version.id,
        version=version.version,
        algorithm=version.algorithm,
        is_active=version.is_active,
        test_period=version.test_period,
        champion=details.get("champion", {}),
        comparison=details.get("comparison", []),
        rule_floors=details.get("rule_floors", {}),
        bands=details.get("bands", []),
        evaluation=details.get("evaluation"),
    )


def activate(db: Session, registry: ModelRegistry, version_id: int, user: User) -> ModelVersion:
    previous = db.scalar(select(ModelVersion.version).where(ModelVersion.is_active))
    version = registry.activate(db, version_id)
    audit.record(
        db,
        user,
        "model.activate",
        "model_version",
        version.id,
        before={"active": previous},
        after={"active": version.version},
    )
    db.commit()
    db.refresh(version)
    return version


def sync(db: Session, registry: ModelRegistry, user: User) -> list[ModelVersion]:
    before = set(db.scalars(select(ModelVersion.version)))
    registry.sync(db)
    versions = list_versions(db)
    added = sorted({v.version for v in versions} - before)
    if added:
        audit.record(db, user, "model.register", "model_version", after={"added": added})
        db.commit()
    return versions
