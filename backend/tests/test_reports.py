import csv
import io

from .test_predictions import submission

API = "/api/v1"


def _export(client, auth, **params):
    resp = client.get(f"{API}/reports/export", params=params, headers=auth())
    assert resp.status_code == 200, resp.text
    return resp, list(csv.DictReader(io.StringIO(resp.text)))


def test_export_uses_the_transaction_filters(client, loaded, auth):
    resp, rows = _export(client, auth, period="202608", band=["high", "critical"])
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="transactions_202608.csv"' in resp.headers["content-disposition"]
    listed = client.get(
        f"{API}/transactions",
        params={"period": "202608", "band": ["high", "critical"], "page_size": 1},
        headers=auth(),
    ).json()
    assert len(rows) == listed["total"] > 0
    first = rows[0]
    assert first["period"] == "202608" and int(first["risk_score"]) >= 70
    assert first["break_types"]  # joined with ';'
    priorities = [int(r["priority"]) for r in rows]
    assert priorities == sorted(priorities, reverse=True)


def test_export_neutralises_spreadsheet_formulas(client, loaded, auth):
    body = submission(description="=HYPERLINK(1)", amount=-5.0)
    assert client.post(f"{API}/predictions", json=body, headers=auth()).status_code == 201
    _, rows = _export(client, auth, search="ABCDEF0123456789")
    assert rows[0]["description"] == "'=HYPERLINK(1)"
    assert rows[0]["amount"] == "-5.0"  # numbers stay numbers


def test_export_needs_a_login_and_a_known_format(client, loaded, auth):
    assert client.get(f"{API}/reports/export").status_code == 401
    resp = client.get(f"{API}/reports/export", params={"format": "pdf"}, headers=auth())
    assert resp.status_code == 422
