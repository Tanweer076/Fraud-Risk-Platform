"""Load a saved model and score linked transactions."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from fraudml.features.build import build_features
from fraudml.labels.break_labeller import label_breaks
from fraudml.scoring.explain import break_reason, contributions, top_factors
from fraudml.scoring.materiality import exposure, priority, to_usd
from fraudml.scoring.risk import risk_score


class Scorer:
    def __init__(self, artifact: dict):
        self.artifact = artifact
        self.pipeline = artifact["pipeline"]
        self.calibrator = artifact["calibrator"]
        self.features = artifact["features"]
        self.version = artifact["version"]
        self.metadata = artifact.get("metadata", {})

    @classmethod
    def load(cls, path: str | Path) -> "Scorer":
        return cls(joblib.load(path))

    def score(
        self,
        linked: pd.DataFrame,
        history: pd.DataFrame | None = None,
        k: int = 5,
        explain_min_score: int = 0,
    ) -> pd.DataFrame:
        """Score rows of the linked frame (see fraudml.canonical.link).

        Returns per row: probability, model_score, risk_score and band; exposure_usd (money at
        stake) and priority (risk weighted by exposure); break_types and rule_hits
        (deterministic checks with reasons); top_factors (model explanation).
        Explanations are the slow part of batch scoring, so only rows with a risk score of at
        least `explain_min_score` get top_factors; the others get an empty list.
        `history` holds earlier transactions of the same accounts, excluding these rows.
        """
        original_index = linked.index
        labelled = label_breaks(linked.reset_index(drop=True))
        features = build_features(labelled, history)
        X = features[self.features]
        proba = self.calibrator.predict_proba(X)[:, 1]

        breaks = [list(b) for b in labelled["break_types"]]
        scores = [risk_score(float(p), b) for p, b in zip(proba, breaks, strict=True)]
        explain = np.array([s[0] >= explain_min_score for s in scores])
        contrib = contributions(self.pipeline, X[explain]) if explain.any() else None

        # Row context (values used in reasons) only for rows that need a reason; building it
        # for every row would dominate batch time.
        needs_context = explain | np.array([bool(b) for b in breaks])
        context = pd.concat(
            [labelled, features.drop(columns=labelled.columns, errors="ignore")], axis=1
        )
        rows = dict(
            zip(
                np.flatnonzero(needs_context),
                context[needs_context].to_dict("records"),
                strict=True,
            )
        )
        explained_at = {i: j for j, i in enumerate(np.flatnonzero(explain))}
        ids = labelled["transaction_id"].to_numpy()
        amount = features["amount"].to_numpy()
        absdiff = features["max_amt_absdiff"].to_numpy()
        currency = features["currency"].to_numpy()

        out = []
        for i, (score, model_score, band) in enumerate(scores):
            at_stake = exposure(amount[i], absdiff[i], breaks[i])
            exposure_usd = round(to_usd(at_stake, currency[i]), 2) if at_stake else 0.0
            row = rows.get(i)
            out.append(
                {
                    "transaction_id": ids[i],
                    "probability": round(float(proba[i]), 4),
                    "model_score": model_score,
                    "risk_score": score,
                    "band": band,
                    "exposure_usd": exposure_usd,
                    "priority": priority(score, exposure_usd),
                    "break_types": breaks[i],
                    "rule_hits": [
                        {"break_type": t, "reason": break_reason(t, row)} for t in breaks[i]
                    ],
                    "top_factors": (
                        top_factors(contrib.iloc[explained_at[i]], row, k) if explain[i] else []
                    ),
                    "model_version": self.version,
                }
            )
        return pd.DataFrame(out, index=original_index)
