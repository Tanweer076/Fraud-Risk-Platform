"""Model registry: saved fraudml artifacts on disk, their rows in model_versions, the loaded one.

Artifacts live in MODEL_DIR as model_vN/{model.joblib, metadata.json}, with LATEST naming the
newest. On startup every artifact is registered; the active version (or LATEST, if none is
active yet) is loaded. Activating another version swaps it in without a restart. Each scoring
call checks the active version in the database, so every API worker follows an activation.
"""

import json
import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fraudml.scoring.scorer import Scorer
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFound, Unavailable
from app.models import ModelVersion

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedModel:
    id: int
    version: str
    scorer: Scorer


def json_safe(value):
    """NaN and infinity are not valid JSON (or JSONB); store them as null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


class ModelRegistry:
    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self._lock = threading.Lock()
        self._loaded: LoadedModel | None = None

    def sync(self, db: Session) -> None:
        """Register artifacts found on disk and load the active version."""
        for meta_path in sorted(self.model_dir.glob("model_v*/metadata.json")):
            self._register(db, meta_path)
        db.flush()

        active = db.scalar(select(ModelVersion).where(ModelVersion.is_active))
        if active is None:
            active = self._default_version(db)
            if active is not None:
                self._set_active(db, active)
        db.commit()
        if active is None:
            log.warning("No model artifacts in %s; scoring is unavailable", self.model_dir)
        elif Path(active.artifact_path).exists():
            self._load(active)
        else:
            log.error("Active model %s has no artifact at %s", active.version, active.artifact_path)

    def _register(self, db: Session, meta_path: Path) -> None:
        meta = json_safe(json.loads(meta_path.read_text()))
        artifact = meta_path.parent / "model.joblib"
        if not artifact.exists():
            log.warning("Skipping %s: no model.joblib next to it", meta_path.parent)
            return
        champion = meta["champion"]
        values = {
            "algorithm": champion["model"],
            "artifact_path": str(artifact.resolve()),
            "features": meta["features"],
            "threshold": float(champion["threshold"]),
            "metrics": {
                "test": champion["test"],
                "test_with_rule_floors": champion["test_hybrid_high_or_above"],
            },
            "train_periods": meta["train_periods"],
            "test_period": meta["test_period"],
            "details": meta,
            "trained_at": datetime.fromisoformat(meta["created_at"]),
        }
        row = db.scalar(select(ModelVersion).where(ModelVersion.version == meta["version"]))
        if row is None:
            db.add(ModelVersion(version=meta["version"], **values))
            log.info("Registered model %s", meta["version"])
        else:
            for key, value in values.items():
                setattr(row, key, value)

    def _default_version(self, db: Session) -> ModelVersion | None:
        latest = self.model_dir / "LATEST"
        if latest.exists():
            row = db.scalar(
                select(ModelVersion).where(ModelVersion.version == latest.read_text().strip())
            )
            if row is not None:
                return row
        return db.scalar(select(ModelVersion).order_by(ModelVersion.trained_at.desc()).limit(1))

    @staticmethod
    def _set_active(db: Session, version: ModelVersion) -> None:
        # Two statements, so the one-active unique index never sees two active rows.
        db.execute(update(ModelVersion).where(ModelVersion.is_active).values(is_active=False))
        db.execute(update(ModelVersion).where(ModelVersion.id == version.id).values(is_active=True))
        db.refresh(version)

    def _load(self, version: ModelVersion) -> LoadedModel:
        loaded = LoadedModel(version.id, version.version, Scorer.load(version.artifact_path))
        with self._lock:
            self._loaded = loaded
        log.info("Loaded model %s", version.version)
        return loaded

    def activate(self, db: Session, version_id: int) -> ModelVersion:
        version = db.get(ModelVersion, version_id)
        if version is None:
            raise NotFound(f"Model version {version_id} not found")
        if not Path(version.artifact_path).exists():
            raise Unavailable(f"The artifact for {version.version} is missing on disk")
        self._set_active(db, version)
        self._load(version)
        return version

    def current(self, db: Session) -> LoadedModel:
        """The active model, reloaded if another worker activated a different version."""
        active = db.execute(
            select(ModelVersion.id, ModelVersion.artifact_path).where(ModelVersion.is_active)
        ).first()
        if active is None:
            raise Unavailable("No active model. Train one with `fraudml train` and restart.")
        with self._lock:
            loaded = self._loaded
        if loaded is None or loaded.id != active.id:
            if not Path(active.artifact_path).exists():
                raise Unavailable("The active model's artifact is missing on disk")
            loaded = self._load(db.get(ModelVersion, active.id))
        return loaded

    @property
    def loaded_version(self) -> str | None:
        with self._lock:
            return self._loaded.version if self._loaded else None
