"""Evaluation data saved with a model for the Models page: curves, confusion, importance."""

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve
from sklearn.pipeline import Pipeline

from fraudml.scoring.explain import contributions

MAX_POINTS = 100
IMPORTANCE_SAMPLE = 5000


def _thin(*arrays: np.ndarray, max_points: int = MAX_POINTS) -> list[np.ndarray]:
    """Keep at most max_points evenly spaced points, always including both ends."""
    n = len(arrays[0])
    idx = np.unique(np.linspace(0, n - 1, min(n, max_points)).round().astype(int))
    return [np.asarray(a)[idx] for a in arrays]


def _r(v: float) -> float:
    return round(float(v), 4)


def pr_curve(y, p) -> list[dict]:
    precision, recall, thresholds = precision_recall_curve(y, p)
    thresholds = np.append(thresholds, 1.0)  # the last (recall 0) point has no threshold
    return [
        {"precision": _r(a), "recall": _r(b), "threshold": _r(t)}
        for a, b, t in zip(*_thin(precision, recall, thresholds), strict=True)
    ]


def roc_points(y, p) -> list[dict]:
    fpr, tpr, thresholds = roc_curve(y, p)
    thresholds = np.clip(thresholds, 0.0, 1.0)  # the first threshold is +inf
    return [
        {"fpr": _r(a), "tpr": _r(b), "threshold": _r(t)}
        for a, b, t in zip(*_thin(fpr, tpr, thresholds), strict=True)
    ]


def confusion(y, flagged) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, flagged, labels=[0, 1]).ravel()
    return {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)}


def calibration(y, p, n_bins: int = 10) -> list[dict]:
    """Mean predicted probability vs observed rate per probability bin (empty bins left out)."""
    y, p = np.asarray(y), np.asarray(p)
    bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
    return [
        {
            "bin_from": _r(b / n_bins),
            "bin_to": _r((b + 1) / n_bins),
            "predicted": _r(p[bins == b].mean()),
            "observed": _r(y[bins == b].mean()),
            "count": int((bins == b).sum()),
        }
        for b in range(n_bins)
        if (bins == b).any()
    ]


def score_histogram(scores, width: int = 10) -> list[dict]:
    """Counts of 0-100 risk scores in bins of `width` (the last bin includes 100)."""
    edges = list(range(0, 100 + width, width))
    counts, _ = np.histogram(np.asarray(scores), bins=edges)
    return [
        {"score_from": lo, "score_to": hi if hi == 100 else hi - 1, "count": int(c)}
        for lo, hi, c in zip(edges[:-1], edges[1:], counts, strict=True)
    ]


def feature_importance(pipeline: Pipeline, X: pd.DataFrame, top: int = 15) -> list[dict]:
    """Mean absolute contribution (log-odds) per raw feature over a sample of rows."""
    if len(X) > IMPORTANCE_SAMPLE:
        X = X.sample(IMPORTANCE_SAMPLE, random_state=0)
    importance = contributions(pipeline, X).abs().mean().sort_values(ascending=False)
    return [
        {"feature": name, "mean_abs_contribution": _r(value)}
        for name, value in importance.head(top).items()
    ]
