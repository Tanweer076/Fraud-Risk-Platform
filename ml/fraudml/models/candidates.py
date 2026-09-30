"""Candidate models, each a scikit-learn Pipeline over the same feature frame."""

import lightgbm as lgb
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from fraudml.features.build import CATEGORICAL

SEED = 42


def _preprocess(numeric: list[str], categorical: list[str], scale: bool) -> ColumnTransformer:
    num_steps = [("impute", SimpleImputer(strategy="median", keep_empty_features=True))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    transformers = [("num", Pipeline(num_steps), numeric)]
    if categorical:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers, verbose_feature_names_out=True)


def make_candidates(features: list[str], pos_weight: float) -> dict[str, Pipeline]:
    """Supervised candidates. `pos_weight` = negatives / positives in the training data."""
    categorical = [f for f in features if f in CATEGORICAL]
    numeric = [f for f in features if f not in CATEGORICAL]
    return {
        "logistic_regression": Pipeline(
            [
                ("prep", _preprocess(numeric, categorical, scale=True)),
                (
                    "model",
                    LogisticRegression(class_weight="balanced", max_iter=2000, random_state=SEED),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("prep", _preprocess(numeric, categorical, scale=False)),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=2,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=SEED,
                    ),
                ),
            ]
        ),
        "lightgbm": Pipeline(
            [
                ("prep", _preprocess(numeric, categorical, scale=False)),
                (
                    "model",
                    lgb.LGBMClassifier(
                        n_estimators=400,
                        learning_rate=0.05,
                        num_leaves=31,
                        min_child_samples=20,
                        subsample=0.8,
                        subsample_freq=1,
                        colsample_bytree=0.8,
                        scale_pos_weight=pos_weight,
                        random_state=SEED,
                        verbose=-1,
                    ),
                ),
            ]
        ),
    }


# Models that can explain individual predictions (see fraudml.scoring.explain).
EXPLAINABLE = {"logistic_regression", "lightgbm"}


def make_isolation_forest(numeric: list[str]) -> Pipeline:
    """Unsupervised detector; labels are never used to fit it."""
    return Pipeline(
        [
            ("prep", _preprocess(numeric, [], scale=True)),
            (
                "model",
                IsolationForest(
                    n_estimators=300, contamination="auto", random_state=SEED, n_jobs=-1
                ),
            ),
        ]
    )
