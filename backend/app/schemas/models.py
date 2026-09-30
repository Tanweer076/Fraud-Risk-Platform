from datetime import datetime

from pydantic import BaseModel, computed_field

from app.schemas.common import ORMModel


class ModelVersionOut(ORMModel):
    id: int
    version: str
    algorithm: str
    is_active: bool
    threshold: float
    metrics: dict
    train_periods: list[str]
    test_period: str
    features: list[str]
    trained_at: datetime | None
    registered_at: datetime

    @computed_field
    @property
    def n_features(self) -> int:
        return len(self.features)


class ModelEvaluation(BaseModel):
    id: int
    version: str
    algorithm: str
    is_active: bool
    test_period: str
    champion: dict
    comparison: list[dict]
    rule_floors: dict[str, int]
    bands: list
    evaluation: dict | None  # curves, confusion matrices, importance; absent in older artifacts
