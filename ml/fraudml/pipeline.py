"""Command-line pipeline.

    fraudml label --month-dir "data/raw/OneRecon_DataSet/Historical Data/july" \
                  --rules data/raw/OneRecon_DataSet/business_rules.txt --out data/processed

    fraudml eda --processed data/processed --out ml/reports/eda_report.html

For each month folder `label` will: ingest GL, MA and FA, validate business rules, link the systems,
derive break labels, write `labelled_<period>.parquet` and print a JSON summary.
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd

from fraudml.canonical.link import link_systems
from fraudml.errors import IngestionError
from fraudml.ingest.fa_csv import read_fa_csv
from fraudml.ingest.gl_xml import read_gl_xml
from fraudml.ingest.join_map import read_join_map
from fraudml.ingest.ma_api import read_ma_api, read_ma_embedded
from fraudml.ingest.rules import parse_rules, validate
from fraudml.labels.break_labeller import label_breaks, summarise

log = logging.getLogger("fraudml")


def _one(month_dir: Path, pattern: str) -> Path:
    matches = sorted(month_dir.glob(pattern))
    if len(matches) != 1:
        raise IngestionError(f"Expected one {pattern} in {month_dir}, found {len(matches)}")
    return matches[0]


def label_month(
    month_dir: Path, rules_path: Path, ma_source: str = "embedded", ma_url: str | None = None
) -> tuple[str, pd.DataFrame]:
    gl_path = _one(month_dir, "gl_report_*.xml")
    period = re.search(r"(\d{6})", gl_path.name).group(1)
    rules = parse_rules(rules_path)

    started = time.perf_counter()
    records = {
        "gl": read_gl_xml(gl_path),
        "fa": read_fa_csv(_one(month_dir, "fa_report_*.csv")),
        "ma": (
            read_ma_api(ma_url)
            if ma_source == "api"
            else read_ma_embedded(_one(month_dir, "ma_api_server_*.py"))
        ),
    }
    join_map = read_join_map(_one(month_dir, "join_map.txt"))
    for system, df in records.items():
        df["rule_violations"] = validate(df, rules, period=period)
        log.info("%s %s: %d records", period, system.upper(), len(df))
    log.info("%s ingested in %.1fs", period, time.perf_counter() - started)

    return period, label_breaks(link_systems(records, join_map))


def run_eda(processed: Path, out: Path) -> int:
    from fraudml.eda.report import write_report  # matplotlib is only needed here

    try:
        path = write_report(processed, out)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1
    log.info("EDA report written to %s", path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fraudml")
    sub = parser.add_subparsers(dest="command", required=True)
    lab = sub.add_parser("label", help="Ingest month folders and derive break labels")
    lab.add_argument("--month-dir", type=Path, action="append", required=True)
    lab.add_argument("--rules", type=Path, required=True)
    lab.add_argument("--out", type=Path, default=Path("data/processed"))
    lab.add_argument("--ma-source", choices=["embedded", "api"], default="embedded")
    lab.add_argument("--ma-url", default="http://localhost:5000")
    eda = sub.add_parser("eda", help="Write the EDA HTML report from labelled parquet files")
    eda.add_argument("--processed", type=Path, default=Path("data/processed"))
    eda.add_argument("--out", type=Path, default=Path("ml/reports/eda_report.html"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "eda":
        return run_eda(args.processed, args.out)
    if args.ma_source == "api" and len(args.month_dir) > 1:
        parser.error("--ma-source api serves one month at a time; pass a single --month-dir")

    args.out.mkdir(parents=True, exist_ok=True)
    summaries = {}
    try:
        for month_dir in args.month_dir:
            period, labelled = label_month(month_dir, args.rules, args.ma_source, args.ma_url)
            labelled.to_parquet(args.out / f"labelled_{period}.parquet", index=False)
            summaries[period] = summarise(labelled)
    except IngestionError as exc:
        log.error("%s", exc)
        return 1
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
