"""Train, compare, calibrate and save the risk model.

Split: the latest month is the out-of-time test set. Earlier months are split 80/20
(stratified) into train and validation. Validation picks the champion, fits the isotonic
calibrator and sets the decision threshold; the test month is only used for reporting.
"""

import json
import logging
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.model_selection import train_test_split

from fraudml import __version__
from fraudml.eda.analysis import load_labelled
from fraudml.features.build import (
    ALL_FEATURES,
    ATTRIBUTE_NUMERIC,
    BEHAVIOURAL,
    CATEGORICAL,
    CROSS_SYSTEM,
    RULES,
    build_features,
)
from fraudml.labels.break_labeller import BREAK_TYPES
from fraudml.models.candidates import (
    EXPLAINABLE,
    SEED,
    make_candidates,
    make_isolation_forest,
)
from fraudml.models.evaluation import (
    calibration,
    confusion,
    feature_importance,
    pr_curve,
    roc_points,
    score_histogram,
)
from fraudml.models.metrics import best_f1_threshold, evaluate
from fraudml.scoring.risk import BANDS, RULE_FLOORS, risk_score

log = logging.getLogger("fraudml")

ABLATION_FEATURES = BEHAVIOURAL + ATTRIBUTE_NUMERIC + CATEGORICAL
ANOMALY_FEATURES = CROSS_SYSTEM + RULES


def _next_version(out_dir: Path) -> str:
    existing = [
        int(p.name.removeprefix("model_v"))
        for p in out_dir.glob("model_v*")
        if p.name.removeprefix("model_v").isdigit()
    ]
    return f"model_v{max(existing, default=0) + 1}"


def _per_type_recall(df: pd.DataFrame, flagged: np.ndarray) -> dict:
    out = {}
    for t in BREAK_TYPES:
        mask = df[f"brk_{t}"].to_numpy()
        if mask.sum():
            out[t] = {"n": int(mask.sum()), "recall": float(flagged[mask].mean())}
    return out


def train(processed_dir: str | Path, out_dir: str | Path, test_period: str | None = None) -> dict:
    started = time.perf_counter()
    df = load_labelled(processed_dir)
    X = build_features(df)
    y = df["is_suspicious"].astype(int).to_numpy()

    periods = sorted(df["period"].unique())
    test_period = test_period or periods[-1]
    is_test = (df["period"] == test_period).to_numpy()
    earlier = (df["period"] < test_period).to_numpy()
    if not earlier.any() or y[earlier].sum() < 10:
        raise ValueError("Need at least 10 suspicious transactions before the test month")

    tr_idx, va_idx = train_test_split(
        np.flatnonzero(earlier), test_size=0.2, stratify=y[earlier], random_state=SEED
    )
    te_idx = np.flatnonzero(is_test)
    pos_weight = float((y[tr_idx] == 0).sum() / max(y[tr_idx].sum(), 1))
    log.info(
        "train %d (%d pos), val %d (%d pos), test %s %d (%d pos)",
        len(tr_idx),
        y[tr_idx].sum(),
        len(va_idx),
        y[va_idx].sum(),
        test_period,
        len(te_idx),
        y[te_idx].sum(),
    )

    results, fitted = [], {}

    def _run(name: str, pipe, features: list[str], note: str = "") -> None:
        pipe.fit(X.iloc[tr_idx][features], y[tr_idx])
        p_va = pipe.predict_proba(X.iloc[va_idx][features])[:, 1]
        p_te = pipe.predict_proba(X.iloc[te_idx][features])[:, 1]
        thr = best_f1_threshold(y[va_idx], p_va)
        results.append(
            {
                "model": name,
                "features": note or "all",
                "threshold": thr,
                "val": evaluate(y[va_idx], p_va, thr),
                "test": evaluate(y[te_idx], p_te, thr),
            }
        )
        fitted[name] = pipe
        log.info(
            "%s: val PR-AUC %.4f, test PR-AUC %.4f",
            name,
            results[-1]["val"]["pr_auc"],
            results[-1]["test"]["pr_auc"],
        )

    for name, pipe in make_candidates(ALL_FEATURES, pos_weight).items():
        _run(name, pipe, ALL_FEATURES)

    ablation = make_candidates(ABLATION_FEATURES, pos_weight)["lightgbm"]
    _run("lightgbm_ablation", ablation, ABLATION_FEATURES, note="behavioural + attributes only")

    # Unsupervised: fit on the training rows without their labels; higher = more anomalous.
    # (A clean month alone has no variance in cross-system features to learn from.)
    iso = make_isolation_forest(ANOMALY_FEATURES).fit(X.iloc[tr_idx][ANOMALY_FEATURES])
    s_va = -iso.score_samples(X.iloc[va_idx][ANOMALY_FEATURES])
    s_te = -iso.score_samples(X.iloc[te_idx][ANOMALY_FEATURES])
    thr = best_f1_threshold(y[va_idx], s_va)
    results.append(
        {
            "model": "isolation_forest",
            "features": "cross-system + rules, no labels",
            "threshold": thr,
            "val": evaluate(y[va_idx], s_va, thr),
            "test": {k: v for k, v in evaluate(y[te_idx], s_te, thr).items() if k != "brier"},
        }
    )
    results[-1]["val"].pop("brier")

    eligible = [r for r in results if r["model"] in EXPLAINABLE]
    champ = max(eligible, key=lambda r: (r["val"]["pr_auc"], -r["val"]["brier"]))
    champ_name = champ["model"]
    pipeline = fitted[champ_name]

    calibrator = CalibratedClassifierCV(FrozenEstimator(pipeline), method="isotonic")
    calibrator.fit(X.iloc[va_idx][ALL_FEATURES], y[va_idx])
    pc_va = calibrator.predict_proba(X.iloc[va_idx][ALL_FEATURES])[:, 1]
    pc_te = calibrator.predict_proba(X.iloc[te_idx][ALL_FEATURES])[:, 1]
    cal_thr = best_f1_threshold(y[va_idx], pc_va)

    test_df = df.iloc[te_idx]
    model_flag = pc_te >= cal_thr
    hybrid_scores = np.array(
        [
            risk_score(float(p), list(b))[0]
            for p, b in zip(pc_te, test_df["break_types"], strict=True)
        ]
    )
    hybrid_flag = hybrid_scores >= 70
    champion = {
        "model": champ_name,
        "threshold": cal_thr,
        "val": evaluate(y[va_idx], pc_va, cal_thr),
        "test": evaluate(y[te_idx], pc_te, cal_thr),
        "test_hybrid_high_or_above": evaluate(y[te_idx], hybrid_scores / 100, 0.70),
        "test_recall_by_break_type": {
            "model_only": _per_type_recall(test_df, model_flag),
            "with_rule_floors": _per_type_recall(test_df, hybrid_flag),
        },
        "test_band_counts": pd.Series(
            [
                risk_score(float(p), list(b))[2]
                for p, b in zip(pc_te, test_df["break_types"], strict=True)
            ]
        )
        .value_counts()
        .to_dict(),
    }

    out_dir = Path(out_dir)
    version = _next_version(out_dir)
    target = out_dir / version
    target.mkdir(parents=True, exist_ok=True)
    metadata = {
        "version": version,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "fraudml_version": __version__,
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "train_periods": [p for p in periods if p < test_period],
        "test_period": test_period,
        "n_train": int(len(tr_idx)),
        "n_val": int(len(va_idx)),
        "n_test": int(len(te_idx)),
        "features": ALL_FEATURES,
        "rule_floors": RULE_FLOORS,
        "bands": BANDS,
        "champion": champion,
        "comparison": results,
        "evaluation": {
            "period": test_period,
            "pr_curve": pr_curve(y[te_idx], pc_te),
            "roc_curve": roc_points(y[te_idx], pc_te),
            "calibration": calibration(y[te_idx], pc_te),
            "confusion_model": confusion(y[te_idx], model_flag),
            "confusion_with_rule_floors": confusion(y[te_idx], hybrid_flag),
            "score_histogram": score_histogram(hybrid_scores),
            "feature_importance": feature_importance(pipeline, X.iloc[te_idx][ALL_FEATURES]),
        },
        "train_seconds": round(time.perf_counter() - started, 1),
    }
    joblib.dump(
        {
            "version": version,
            "pipeline": pipeline,
            "calibrator": calibrator,
            "features": ALL_FEATURES,
            "threshold": cal_thr,
            "metadata": metadata,
        },
        target / "model.joblib",
    )
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2, default=float))
    (target / "model_report.md").write_text(render_report(metadata))
    (out_dir / "LATEST").write_text(version + "\n")
    log.info("Saved %s (champion %s) in %.1fs", target, champ_name, metadata["train_seconds"])
    return metadata


def _pct(v: float) -> str:
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.1%}"


def render_report(meta: dict) -> str:
    c = meta["champion"]
    lines = [
        f"# Model report: {meta['version']}",
        "",
        f"Trained on {', '.join(meta['train_periods'])} ({meta['n_train']:,} train / "
        f"{meta['n_val']:,} validation rows); tested out-of-time on {meta['test_period']} "
        f"({meta['n_test']:,} rows).",
        "",
        "## Model comparison",
        "",
        "| Model | Features | Val PR-AUC | Test PR-AUC | Test ROC-AUC | Test recall@P90 | "
        "Test precision | Test recall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in meta["comparison"]:
        v, t = r["val"], r["test"]
        lines.append(
            f"| {r['model']} | {r['features']} | {v['pr_auc']:.3f} | {t['pr_auc']:.3f} | "
            f"{t['roc_auc']:.3f} | {_pct(t['recall_at_p90'])} | {_pct(t['precision'])} | "
            f"{_pct(t['recall'])} |"
        )
    t, h = c["test"], c["test_hybrid_high_or_above"]
    lines += [
        "",
        f"## Champion: {c['model']} (isotonic-calibrated)",
        "",
        f"Decision threshold {c['threshold']:.3f} (best F1 on validation).",
        "",
        "| Test month | Precision | Recall | F1 | Brier |",
        "|---|---|---|---|---|",
        f"| Model only | {_pct(t['precision'])} | {_pct(t['recall'])} | {_pct(t['f1'])} | "
        f"{t['brier']:.4f} |",
        f"| With rule floors (score ≥ 70) | {_pct(h['precision'])} | {_pct(h['recall'])} | "
        f"{_pct(h['f1'])} | – |",
        "",
        "### Recall by break type (test month)",
        "",
        "| Break type | Transactions | Model only | With rule floors |",
        "|---|---|---|---|",
    ]
    mo, wf = (
        c["test_recall_by_break_type"]["model_only"],
        c["test_recall_by_break_type"]["with_rule_floors"],
    )
    for k, v in mo.items():
        lines.append(f"| {k} | {v['n']:,} | {_pct(v['recall'])} | {_pct(wf[k]['recall'])} |")
    lines += ["", "### Risk bands (test month)", "", "| Band | Transactions |", "|---|---|"]
    for band in ("critical", "high", "medium", "low"):
        lines.append(f"| {band} | {c['test_band_counts'].get(band, 0):,} |")
    return "\n".join(lines) + "\n"
