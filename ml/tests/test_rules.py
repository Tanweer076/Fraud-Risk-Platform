import pytest

from fraudml.errors import IngestionError
from fraudml.ingest.gl_xml import read_gl_xml
from fraudml.ingest.ma_api import read_ma_embedded
from fraudml.ingest.rules import parse_rules, validate

from .conftest import BASE, write_month


def test_parse_rules_reads_every_line(rules_path):
    rules = parse_rules(rules_path)
    assert [r.rule_id for r in rules][:3] == ["R01", "R02", "R03"]
    assert rules[3].rule_type == "RANGE"


def test_parse_rules_rejects_malformed_line(tmp_path):
    path = tmp_path / "rules.txt"
    path.write_text("R01|TransactionID|REGEX\n")
    with pytest.raises(IngestionError, match="line 1"):
        parse_rules(path)


def test_clean_records_have_no_violations(tmp_path, rules_path):
    gl = read_gl_xml(write_month(tmp_path) / "gl_report_202607.xml")
    result = validate(gl, parse_rules(rules_path), period="202607")
    assert result.map(len).sum() == 0


def test_each_row_rule_is_enforced(tmp_path, rules_path):
    rows = [
        ("bad-id", "ACC0001", "2026-07-03", "10.00", "USD", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA2", "XYZ0002", "2026-07-03", "10.00", "USD", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA3", "ACC0003", "03/07/2026", "10.00", "USD", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA4", "ACC0004", "2026-07-03", "-5.00", "USD", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA5", "ACC0005", "2026-07-03", "10.00", "XXX", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA6", "ACC0006", "2026-07-03", "10.00", "USD", "ZZ", "Vendor payment"),
        ("AAAAAAAAAAAAAAA7", "ACC0007", "2026-07-03", "10.00", "USD", "US", "Fee"),
        ("AAAAAAAAAAAAAAA8", "ACC0008", "2026-08-01", "10.00", "USD", "US", "Vendor payment"),
        ("AAAAAAAAAAAAAAA9", "ACC0009", "2026-07-03", "100000.01", "USD", "US", "Vendor payment"),
    ]
    gl = read_gl_xml(write_month(tmp_path, gl_rows=rows) / "gl_report_202607.xml")
    result = validate(gl, parse_rules(rules_path), period="202607").tolist()
    assert result == [
        ["R01"],
        ["R02"],
        ["R03"],
        ["R04"],
        ["R05"],
        ["R06"],
        ["R07"],
        ["PERIOD"],
        ["R04"],
    ]


def test_account_format_rule_only_applies_to_gl(tmp_path, rules_path):
    ma = read_ma_embedded(write_month(tmp_path, ma_rows=BASE) / "ma_api_server_202607.py")
    result = validate(ma, parse_rules(rules_path), period="202607")
    assert result.map(len).sum() == 0
