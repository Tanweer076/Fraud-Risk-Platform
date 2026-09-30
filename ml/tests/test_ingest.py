import httpx
import pytest

from fraudml.errors import IngestionError
from fraudml.ingest.fa_csv import read_fa_csv
from fraudml.ingest.gl_xml import read_gl_xml
from fraudml.ingest.join_map import read_join_map
from fraudml.ingest.ma_api import read_ma_api, read_ma_embedded

from .conftest import write_month


def test_gl_fa_ma_read_into_canonical_schema(tmp_path):
    month = write_month(tmp_path)
    gl = read_gl_xml(month / "gl_report_202607.xml")
    fa = read_fa_csv(month / "fa_report_202607.csv")
    ma = read_ma_embedded(month / "ma_api_server_202607.py")

    assert list(gl.columns) == list(fa.columns) == list(ma.columns)
    assert len(gl) == len(fa) == len(ma) == 3
    assert gl.loc[0, "account_key"] == "ACC0001"
    assert ma.loc[0, "account_key"] == "CUS-000001"
    assert fa.loc[0, "account_key"] == "FA-000001"
    assert ma["amount"].dtype == "float64"
    assert ma.loc[1, "amount"] == 250.50


def test_embedded_ma_is_decoded_without_running_the_script(tmp_path, capsys):
    month = write_month(tmp_path)
    read_ma_embedded(month / "ma_api_server_202607.py")
    assert "never executed" not in capsys.readouterr().out


def test_invalid_amount_becomes_nan_not_crash(tmp_path):
    rows = [("AAAAAAAAAAAAAAA1", "ACC0001", "2026-07-03", "abc", "USD", "US", "Vendor payment")]
    month = write_month(tmp_path, gl_rows=rows)
    gl = read_gl_xml(month / "gl_report_202607.xml")
    assert gl["amount"].isna().all()


def test_malformed_xml_raises(tmp_path):
    bad = tmp_path / "gl.xml"
    bad.write_text("<GLReport><Transaction>")
    with pytest.raises(IngestionError, match="Cannot read GL XML"):
        read_gl_xml(bad)


def test_missing_column_raises(tmp_path):
    bad = tmp_path / "fa.csv"
    bad.write_text("TransactionID,Amount\nAAAAAAAAAAAAAAA1,1.00\n")
    with pytest.raises(IngestionError, match="missing columns"):
        read_fa_csv(bad)


def test_ma_script_without_payload_raises(tmp_path):
    script = tmp_path / "ma.py"
    script.write_text("print('hi')\n")
    with pytest.raises(IngestionError, match="No embedded MA payload"):
        read_ma_embedded(script)


def test_join_map_with_bad_dates_raises(tmp_path):
    bad = tmp_path / "join_map.txt"
    bad.write_text(
        "gl_account_id,ma_customer_key,fa_key,entity,effective_from,effective_to\n"
        "ACC0001,CUS-000001,FA-000001,Global,not-a-date,2099-12-31\n"
    )
    with pytest.raises(IngestionError, match="invalid effective dates"):
        read_join_map(bad)


def _ma_row(i: int) -> dict:
    return {
        "TransactionID": f"{i:016X}",
        "TransactionDate": "2026-07-01",
        "Amount": f"{i}.00",
        "Currency": "USD",
        "Country": "US",
        "Description": "Vendor payment",
        "ma_customer_key": f"CUS-{i:06d}",
    }


def test_ma_api_follows_pagination():
    rows = [_ma_row(i) for i in range(1, 6)]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        per_page = int(request.url.params["per_page"])
        chunk = rows[(page - 1) * per_page : page * per_page]
        return httpx.Response(200, json={"data": chunk, "total_pages": 3, "page": page})

    client = httpx.Client(base_url="http://ma", transport=httpx.MockTransport(handler))
    df = read_ma_api("http://ma", per_page=2, client=client)
    assert len(df) == 5
    assert df["transaction_id"].tolist() == [r["TransactionID"] for r in rows]


def test_ma_api_error_status_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "per_page must be between 1 and 5000"})

    client = httpx.Client(base_url="http://ma", transport=httpx.MockTransport(handler))
    with pytest.raises(IngestionError, match="MA API returned 400"):
        read_ma_api("http://ma", client=client)
