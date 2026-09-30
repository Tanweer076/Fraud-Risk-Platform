import json

import joblib
import pandas as pd
import pytest

from fraudml.eda.analysis import load_labelled
from fraudml.models.train import train
from fraudml.pipeline import main
from fraudml.scoring.scorer import Scorer

from .conftest import make_dataset


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    from .conftest import RULES

    root = tmp_path_factory.mktemp("ds")
    rules = root / "business_rules.txt"
    rules.write_text(RULES)
    processed = make_dataset(root, rules)
    meta = train(processed, root / "artifacts")
    return root, processed, meta


def test_training_writes_artifact_and_reports(trained):
    root, _, meta = trained
    target = root / "artifacts" / meta["version"]
    assert meta["version"] == "model_v1"
    assert (root / "artifacts" / "LATEST").read_text().strip() == "model_v1"
    for name in ("model.joblib", "metadata.json", "model_report.md"):
        assert (target / name).exists()
    assert json.loads((target / "metadata.json").read_text())["test_period"] == "202608"
    assert "## Model comparison" in (target / "model_report.md").read_text()


def test_comparison_covers_all_candidates(trained):
    _, _, meta = trained
    models = [r["model"] for r in meta["comparison"]]
    assert models == [
        "logistic_regression",
        "random_forest",
        "lightgbm",
        "lightgbm_ablation",
        "isolation_forest",
    ]
    assert meta["champion"]["model"] in {"logistic_regression", "lightgbm"}


def test_models_learn_cross_system_breaks(trained):
    _, _, meta = trained
    champ = meta["champion"]
    assert champ["test"]["pr_auc"] > 0.9
    assert champ["test_hybrid_high_or_above"]["recall"] == pytest.approx(1.0)


def test_second_run_gets_next_version(trained):
    root, processed, _ = trained
    meta = train(processed, root / "artifacts")
    assert meta["version"] == "model_v2"


def _linked(df: pd.DataFrame) -> pd.DataFrame:
    drop = [c for c in df.columns if c.startswith("brk_")] + [
        "break_types",
        "n_break_types",
        "is_suspicious",
        "currency",
        "country",
        "description",
        "transaction_date",
        "amount",
        "account",
        "weekday",
        "amount_band",
        "month_part",
    ]
    return df.drop(columns=drop)


def test_scorer_scores_breaks_high_with_reasons(trained):
    root, processed, _ = trained
    scorer = Scorer.load(root / "artifacts" / "model_v1" / "model.joblib")
    df = load_labelled(processed)
    aug = df[df["period"] == "202608"]
    history = df[df["period"] < "202608"]
    sample = pd.concat([aug[~aug["is_suspicious"]].head(3), aug[aug["is_suspicious"]].head(3)])
    out = scorer.score(_linked(sample), history=history)

    assert list(out.index) == list(sample.index)
    clean, suspicious = out.iloc[:3], out.iloc[3:]
    assert (clean["risk_score"] < 40).all()
    assert (suspicious["risk_score"] >= 70).all()
    for _, row in suspicious.iterrows():
        assert row["break_types"]
        assert all(h["reason"].endswith(".") for h in row["rule_hits"])
    assert set(out.columns) >= {
        "probability",
        "model_score",
        "band",
        "top_factors",
        "model_version",
    }


def test_artifact_contains_pipeline_calibrator_and_features(trained):
    root, _, _ = trained
    artifact = joblib.load(root / "artifacts" / "model_v1" / "model.joblib")
    assert {"pipeline", "calibrator", "features", "threshold", "metadata"} <= set(artifact)


def test_training_needs_positive_examples(tmp_path, rules_path):
    processed = make_dataset(tmp_path, rules_path, break_rates=(0.0, 0.0, 0.1), n=100)
    with pytest.raises(ValueError, match="at least 10 suspicious"):
        train(processed, tmp_path / "artifacts")


def test_cli_train_exit_codes(tmp_path):
    assert main(["train", "--processed", str(tmp_path / "none"), "--out", str(tmp_path / "a")]) == 1
