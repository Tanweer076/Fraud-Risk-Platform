"""Load a saved model and score linked transactions."""

from pathlib import Path

import joblib
import pandas as pd

from fraudml.features.build import build_features
from fraudml.labels.break_labeller import label_breaks
from fraudml.scoring.explain import break_reason, contributions, top_factors
from fraudml.scoring.risk import risk_score


class Scorer:
    def __init__(self, artifact: dict):
        self.artifact = artifact
        self.pipeline = artifact["pipeline"]
        self.calibrator = artifact["calibrator"]
        self.features = artifact["features"]
        self.version = artifact["version"]

    @classmethod
    def load(cls, path: str | Path) -> "Scorer":
        return cls(joblib.load(path))

    def score(
        self, linked: pd.DataFrame, history: pd.DataFrame | None = None, k: int = 5
    ) -> pd.DataFrame:
        """Score rows of the linked frame (see fraudml.canonical.link).

        Returns probability, model_score, risk_score, band, break_types and rule_hits
        (deterministic checks with reasons) and top_factors (model explanation) per row.
        `history` holds earlier transactions of the same accounts, excluding these rows.
        """
        original_index = linked.index
        labelled = label_breaks(linked.reset_index(drop=True))
        X = build_features(labelled, history)[self.features]
        proba = self.calibrator.predict_proba(X)[:, 1]
        contrib = contributions(self.pipeline, X)
        context = pd.concat([labelled, X.drop(columns=labelled.columns, errors="ignore")], axis=1)

        rows = []
        for i, idx in enumerate(labelled.index):
            breaks = list(labelled.at[idx, "break_types"])
            score, model_score, band = risk_score(float(proba[i]), breaks)
            rows.append(
                {
                    "transaction_id": labelled.at[idx, "transaction_id"],
                    "probability": round(float(proba[i]), 4),
                    "model_score": model_score,
                    "risk_score": score,
                    "band": band,
                    "break_types": breaks,
                    "rule_hits": [
                        {"break_type": t, "reason": break_reason(t, context.loc[idx])}
                        for t in breaks
                    ],
                    "top_factors": top_factors(contrib.loc[idx], context.loc[idx], k),
                    "model_version": self.version,
                }
            )
        return pd.DataFrame(rows, index=original_index)
