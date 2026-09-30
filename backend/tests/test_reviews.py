from .conftest import auth_headers, create_users, load_month, make_client

API = "/api/v1"


def _queue(client, auth, **params):
    resp = client.get(f"{API}/reviews/queue", params=params, headers=auth())
    assert resp.status_code == 200
    return resp.json()


def _review(client, auth, transaction_id, decision="confirmed", who="analyst", note="checked"):
    return client.post(
        f"{API}/reviews",
        json={"transaction_id": transaction_id, "decision": decision, "note": note},
        headers=auth(who),
    )


def test_queue_holds_flagged_unreviewed_transactions_by_priority(client, loaded, auth):
    queue = _queue(client, auth, page_size=500)
    assert queue["total"] == 66  # every suspicious synthetic transaction
    scores = [t["risk_score"] for t in queue["items"]]
    assert min(scores) >= 70
    keys = [(t["priority"], t["risk_score"], t["exposure_usd"] or 0) for t in queue["items"]]
    assert keys == sorted(keys, reverse=True)
    assert _queue(client, auth, min_score=0)["total"] == 900


def test_maker_checker_flow(client, loaded, auth, users):
    first = _queue(client, auth)["items"][0]["transaction_id"]

    resp = _review(client, auth, first, note="MA amount is wrong")
    assert resp.status_code == 201
    review = resp.json()
    assert review["status"] == "pending" and review["analyst_email"] == "analyst@example.com"
    assert review["prediction_id"] is not None
    assert _queue(client, auth)["total"] == 65  # out of the queue while pending
    assert _review(client, auth, first, who="analyst2").status_code == 409

    # Only approvers (or admins) decide, and never on their own review.
    assert (
        client.post(
            f"{API}/reviews/{review['id']}/approve", json={}, headers=auth("analyst2")
        ).status_code
        == 403
    )
    own = _review(client, auth, _queue(client, auth)["items"][0]["transaction_id"], who="admin")
    resp = client.post(f"{API}/reviews/{own.json()['id']}/approve", json={}, headers=auth("admin"))
    assert resp.status_code == 403 and "Maker-checker" in resp.json()["detail"]

    resp = client.post(
        f"{API}/reviews/{review['id']}/approve", json={"note": "agreed"}, headers=auth("approver")
    )
    assert resp.status_code == 200
    approved = resp.json()
    assert approved["status"] == "approved" and approved["approver_email"] == "approver@example.com"
    assert approved["decided_at"] is not None

    detail = client.get(f"{API}/transactions/{first}", headers=auth()).json()
    assert detail["review_outcome"] == "confirmed"
    assert [r["status"] for r in detail["reviews"]] == ["approved"]
    again = client.post(f"{API}/reviews/{review['id']}/approve", json={}, headers=auth("approver"))
    assert again.status_code == 409
    assert _review(client, auth, first).status_code == 409  # decided for good

    summary = client.get(f"{API}/analytics/summary", headers=auth()).json()
    assert (summary["confirmed"], summary["pending_approval"]) == (1, 1)


def test_rejected_review_goes_back_to_the_queue(client, loaded, auth):
    target = _queue(client, auth)["items"][0]["transaction_id"]
    review = _review(client, auth, target, decision="false_positive").json()
    no_note = client.post(f"{API}/reviews/{review['id']}/reject", json={}, headers=auth("approver"))
    assert no_note.status_code == 422
    resp = client.post(
        f"{API}/reviews/{review['id']}/reject",
        json={"note": "the MA record is right"},
        headers=auth("approver"),
    )
    assert resp.status_code == 200 and resp.json()["status"] == "rejected"
    assert target in [t["transaction_id"] for t in _queue(client, auth, page_size=500)["items"]]
    detail = client.get(f"{API}/transactions/{target}", headers=auth()).json()
    assert detail["review_outcome"] is None
    assert _review(client, auth, target).status_code == 201  # can be reviewed again


def test_bulk_approve_reports_what_it_skipped(client, loaded, auth):
    targets = [t["transaction_id"] for t in _queue(client, auth, page_size=3)["items"]]
    ids = [_review(client, auth, t).json()["id"] for t in targets[:2]]
    own = _review(client, auth, targets[2], who="admin").json()["id"]
    resp = client.post(
        f"{API}/reviews/bulk-approve",
        json={"review_ids": [*ids, ids[0], own, 9999]},
        headers=auth("admin"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] == ids
    assert {s["id"]: s["reason"] for s in body["skipped"]} == {
        own: "Maker-checker: you cannot approve or reject your own review",
        9999: "Review 9999 not found",
    }
    pending = client.get(f"{API}/reviews", params={"status": "pending"}, headers=auth()).json()
    assert [r["id"] for r in pending["items"]] == [own]


def test_review_rules(client, loaded, auth):
    target = _queue(client, auth)["items"][0]["transaction_id"]
    assert _review(client, auth, target, who="approver").status_code == 403
    assert _review(client, auth, "NOPE").status_code == 404
    bad = client.post(
        f"{API}/reviews",
        json={"transaction_id": target, "decision": "maybe"},
        headers=auth(),
    )
    assert bad.status_code == 422
    for action in ("approve", "reject"):
        resp = client.post(
            f"{API}/reviews/9999/{action}", json={"note": "x"}, headers=auth("approver")
        )
        assert resp.status_code == 404


def test_unscored_transaction_cannot_be_reviewed(settings, tmp_path, dataset):
    unscored = settings.model_copy(update={"model_dir": tmp_path / "none"})
    with make_client(unscored) as client:
        users = create_users(client, unscored)
        load_month(client.app, unscored, dataset / "raw" / "202607")
        auth = auth_headers(users, unscored)
        tx = client.get(f"{API}/transactions", headers=auth()).json()["items"][0]
        assert tx["risk_score"] is None
        resp = _review(client, auth, tx["transaction_id"])
        assert resp.status_code == 409 and "not been scored" in resp.json()["detail"]


def test_review_actions_are_audited(client, loaded, auth, users):
    target = _queue(client, auth)["items"][0]["transaction_id"]
    review = _review(client, auth, target).json()
    client.post(f"{API}/reviews/{review['id']}/approve", json={}, headers=auth("approver"))
    assert client.get(f"{API}/audit", headers=auth("analyst")).status_code == 403
    trail = client.get(f"{API}/audit", params={"entity": "review"}, headers=auth("approver")).json()
    assert [(a["action"], a["user_id"]) for a in trail["items"]] == [
        ("review.approve", users["approver"].id),
        ("review.create", users["analyst"].id),
    ]
    assert trail["items"][0]["entity_id"] == str(review["id"])
    assert trail["items"][0]["after"]["status"] == "approved"
    assert all(a["request_id"] for a in trail["items"])
