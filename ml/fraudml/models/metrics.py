import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def recall_at_precision(y, p, min_precision: float = 0.9) -> float:
    precision, recall, _ = precision_recall_curve(y, p)
    ok = precision >= min_precision
    return float(recall[ok].max()) if ok.any() else 0.0


def best_f1_threshold(y, p) -> float:
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    return float(thresholds[np.argmax(f1[:-1])]) if len(thresholds) else 0.5


def evaluate(y, p, threshold: float) -> dict:
    y = np.asarray(y).astype(int)
    pred = (np.asarray(p) >= threshold).astype(int)
    has_both = 0 < y.sum() < len(y)
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "pr_auc": float(average_precision_score(y, p)) if has_both else float("nan"),
        "roc_auc": float(roc_auc_score(y, p)) if has_both else float("nan"),
        "recall_at_p90": recall_at_precision(y, p) if has_both else float("nan"),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, np.clip(p, 0, 1))),
    }
