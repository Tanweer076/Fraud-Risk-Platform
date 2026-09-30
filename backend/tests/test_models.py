import shutil

from fraudml.models.train import train
from sqlalchemy import update

from app.models import ModelVersion

from .conftest import auth_headers, create_users, load_month, make_client
from .test_predictions import submission

API = "/api/v1"


def test_models_list_and_evaluation(shared):
    models = shared.client.get(f"{API}/models", headers=shared.auth()).json()
    assert [(m["version"], m["is_active"]) for m in models] == [("model_v1", True)]
    model = models[0]
    assert model["n_features"] == 34 and model["test_period"] == "202608"
    assert set(model["metrics"]) == {"test", "test_with_rule_floors"}
    active = shared.client.get(f"{API}/models/active", headers=shared.auth()).json()
    assert active["id"] == model["id"]

    ev = shared.client.get(f"{API}/models/{model['id']}/evaluation", headers=shared.auth())
    assert ev.status_code == 200
    body = ev.json()
    assert [c["model"] for c in body["comparison"]] == [
        "logistic_regression",
        "random_forest",
        "lightgbm",
        "lightgbm_ablation",
        "isolation_forest",
    ]
    assert body["rule_floors"]["rule_violation"] == 90
    curves = body["evaluation"]
    assert {"pr_curve", "roc_curve", "confusion_model", "feature_importance"} <= set(curves)
    missing = shared.client.get(f"{API}/models/99/evaluation", headers=shared.auth())
    assert missing.status_code == 404


def test_a_new_version_is_registered_and_activated(settings, dataset, model_dir_copy):
    train(dataset / "processed", model_dir_copy)  # writes model_v2 next to model_v1
    own = settings.model_copy(update={"model_dir": model_dir_copy})
    with make_client(own) as client:
        auth = auth_headers(create_users(client, own), own)
        load_month(client.app, own, dataset / "raw" / "202608")

        # LATEST names model_v2, so a fresh database starts with it; switch to v1 first.
        versions = {m["version"]: m for m in client.get(f"{API}/models", headers=auth()).json()}
        assert set(versions) == {"model_v1", "model_v2"} and versions["model_v2"]["is_active"]
        v1, v2 = versions["model_v1"]["id"], versions["model_v2"]["id"]

        assert client.post(f"{API}/models/{v1}/activate", headers=auth()).status_code == 403
        resp = client.post(f"{API}/models/{v1}/activate", headers=auth("admin"))
        assert resp.status_code == 200 and resp.json()["is_active"] is True
        assert client.get(f"{API}/ready").json()["model"] == "model_v1"
        first = client.post(f"{API}/predictions", json=submission(), headers=auth()).json()
        assert first["model_version"] == "model_v1"

        client.post(f"{API}/models/{v2}/activate", headers=auth("admin"))
        second = client.post(
            f"{API}/predictions", json=submission("ABCDEF0123456780"), headers=auth()
        ).json()
        assert second["model_version"] == "model_v2"
        active = [m for m in client.get(f"{API}/models", headers=auth()).json() if m["is_active"]]
        assert [m["version"] for m in active] == ["model_v2"]

        trail = client.get(
            f"{API}/audit", params={"action": "model.activate"}, headers=auth("admin")
        ).json()
        assert [a["after"]["active"] for a in trail["items"]] == ["model_v2", "model_v1"]
        assert client.post(f"{API}/models/999/activate", headers=auth("admin")).status_code == 404


def test_activation_by_another_worker_is_picked_up(settings, dataset, model_dir_copy):
    train(dataset / "processed", model_dir_copy)
    own = settings.model_copy(update={"model_dir": model_dir_copy})
    with make_client(own) as client:
        auth = auth_headers(create_users(client, own), own)
        load_month(client.app, own, dataset / "raw" / "202608")
        with client.app.state.sessionmaker() as db:  # what another API process would do
            db.execute(update(ModelVersion).values(is_active=False))
            v1 = ModelVersion.version == "model_v1"
            db.execute(update(ModelVersion).where(v1).values(is_active=True))
            db.commit()
        result = client.post(f"{API}/predictions", json=submission(), headers=auth()).json()
        assert result["model_version"] == "model_v1"
        assert client.get(f"{API}/ready").json()["model"] == "model_v1"


def test_sync_registers_artifacts_added_after_startup(settings, dataset, model_dir_copy):
    own = settings.model_copy(update={"model_dir": model_dir_copy})
    with make_client(own) as client:
        auth = auth_headers(create_users(client, own), own)
        assert len(client.get(f"{API}/models", headers=auth()).json()) == 1
        train(dataset / "processed", model_dir_copy)
        assert client.post(f"{API}/models/sync", headers=auth()).status_code == 403
        resp = client.post(f"{API}/models/sync", headers=auth("admin"))
        assert [m["version"] for m in resp.json()] == ["model_v2", "model_v1"]
        # The running model does not change until someone activates the new one.
        assert client.get(f"{API}/ready").json()["model"] == "model_v1"


def test_activating_a_version_whose_artifact_is_gone_fails_cleanly(
    settings, dataset, model_dir_copy
):
    train(dataset / "processed", model_dir_copy)
    own = settings.model_copy(update={"model_dir": model_dir_copy})
    with make_client(own) as client:
        auth = auth_headers(create_users(client, own), own)
        models = client.get(f"{API}/models", headers=auth()).json()
        versions = {m["version"]: m["id"] for m in models}
        shutil.rmtree(model_dir_copy / "model_v1")
        resp = client.post(f"{API}/models/{versions['model_v1']}/activate", headers=auth("admin"))
        assert resp.status_code == 503
        assert client.get(f"{API}/ready").json()["model"] == "model_v2"
