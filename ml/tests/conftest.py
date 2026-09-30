import base64
import zlib
from pathlib import Path

import pytest

RULES = """R01|TransactionID|REGEX|^[A-F0-9]{16}$$|TransactionID must be 16-char hex
R02|AccountID|REGEX|^ACC\\d{4}$$|AccountID must start with ACC followed by 4 digits
R03|TransactionDate|DATE|%Y-%m-%d|Date must be ISO-8601
R04|Amount|RANGE|0,100000|Amount must be between 0 and 100 000
R05|Currency|LOOKUP|USD,EUR,GBP|Currency must be supported
R06|Country|LOOKUP|US,GB,DE|Country must be valid
R07|Description|REGEX|^.{5,255}$$|Description length 5-255 chars
R08|FILE_PAIR|INGEST|ANY,ANY|Engine can ingest any two files
R10|AGGREGATE|SUM|KEYS=gl_account_id|Aggregate Amount per key
"""

# (TransactionID, gl_account, date, amount, currency, country, description)
BASE = [
    ("AAAAAAAAAAAAAAA1", "ACC0001", "2026-07-03", "100.00", "USD", "US", "Vendor payment"),
    ("AAAAAAAAAAAAAAA2", "ACC0002", "2026-07-04", "250.50", "EUR", "DE", "Advisory fee"),
    ("AAAAAAAAAAAAAAA3", "ACC0003", "2026-07-05", "999.99", "GBP", "GB", "FX settlement"),
]

JOIN_MAP = [
    ("ACC0001", "CUS-000001", "FA-000001"),
    ("ACC0002", "CUS-000002", "FA-000002"),
    ("ACC0003", "CUS-000003", "FA-000003"),
]


def _suffix(acc: str) -> str:
    return acc[3:].zfill(6)


def write_month(
    root: Path,
    gl_rows=BASE,
    ma_rows=BASE,
    fa_rows=BASE,
    join_map=JOIN_MAP,
    period: str = "202607",
) -> Path:
    """Write a month folder in the same layout as the real dataset."""
    month = root / period
    month.mkdir(parents=True)

    txns = "".join(
        f"<Transaction><TransactionID>{t}</TransactionID><gl_account_id>{a}</gl_account_id>"
        f"<TransactionDate>{d}</TransactionDate><Amount>{amt}</Amount>"
        f"<Currency>{c}</Currency><Country>{co}</Country><Description>{desc}</Description>"
        f"</Transaction>"
        for t, a, d, amt, c, co, desc in gl_rows
    )
    (month / f"gl_report_{period}.xml").write_text(
        f"<?xml version='1.0' encoding='UTF-8'?><GLReport period='{period}'>{txns}</GLReport>"
    )

    header = "TransactionID,TransactionDate,Amount,Currency,Country,Description"
    fa_lines = [f"{header},fa_key"] + [
        f"{t},{d},{amt},{c},{co},{desc},FA-{_suffix(a)}" for t, a, d, amt, c, co, desc in fa_rows
    ]
    (month / f"fa_report_{period}.csv").write_text("\n".join(fa_lines) + "\n")

    ma_lines = [f"{header},ma_customer_key"] + [
        f"{t},{d},{amt},{c},{co},{desc},CUS-{_suffix(a)}" for t, a, d, amt, c, co, desc in ma_rows
    ]
    blob = base64.b64encode(zlib.compress("\n".join(ma_lines).encode())).decode()
    (month / f"ma_api_server_{period}.py").write_text(
        f'"""MA server"""\nimport zlib\n\n_DATA = "{blob}"\n\nprint("never executed")\n'
    )

    jm = ["gl_account_id,ma_customer_key,fa_key,entity,effective_from,effective_to"] + [
        f"{g},{m},{f},Global,2022-01-01,2099-12-31" for g, m, f in join_map
    ]
    (month / "join_map.txt").write_text("\n".join(jm) + "\n")
    return month


@pytest.fixture
def rules_path(tmp_path: Path) -> Path:
    path = tmp_path / "business_rules.txt"
    path.write_text(RULES)
    return path


def make_dataset(
    root: Path,
    rules_path: Path,
    periods=("202606", "202607", "202608"),
    n: int = 300,
    break_rates=(0.0, 0.1, 0.1),
    seed: int = 7,
) -> Path:
    """Label a synthetic multi-month dataset and return the processed folder.

    Breaks are injected into MA and FA copies of the GL rows: amount changes, missing FA
    records, currency changes and date shifts, in roughly equal shares.
    """
    import random

    from fraudml.pipeline import label_month

    rng = random.Random(seed)
    currencies = ["USD", "EUR", "GBP"]
    countries = ["US", "GB", "DE"]
    out = root / "processed"
    out.mkdir(parents=True, exist_ok=True)
    counter = 0
    for period, rate in zip(periods, break_rates, strict=True):
        year, month = period[:4], period[4:]
        gl, ma, fa = [], [], []
        for _ in range(n):
            counter += 1
            acc = f"ACC{rng.randint(1, 40):04d}"
            row = (
                f"{counter:016X}",
                acc,
                f"{year}-{month}-{rng.randint(1, 28):02d}",
                f"{rng.uniform(100, 99_000):.2f}",
                rng.choice(currencies),
                rng.choice(countries),
                rng.choice(["Vendor payment", "Advisory fee", "FX settlement"]),
            )
            gl.append(row)
            ma_row, fa_row = list(row), list(row)
            if rng.random() < rate:
                kind = rng.randrange(4)
                if kind == 0:
                    ma_row[3] = f"{float(row[3]) * rng.uniform(1.5, 3):.2f}"
                elif kind == 1:
                    fa_row = None
                elif kind == 2:
                    fa_row[4] = next(c for c in currencies if c != row[4])
                else:
                    ma_row[2] = f"{year}-{month}-{min(28, int(row[2][-2:]) + 5):02d}"
                    if ma_row[2] == row[2]:
                        ma_row[2] = f"{year}-{month}-01"
            ma.append(tuple(ma_row))
            if fa_row is not None:
                fa.append(tuple(fa_row))
        accounts = sorted({r[1] for r in gl})
        join_map = [(a, f"CUS-{a[3:].zfill(6)}", f"FA-{a[3:].zfill(6)}") for a in accounts]
        month_dir = write_month(
            root / "raw", gl_rows=gl, ma_rows=ma, fa_rows=fa, join_map=join_map, period=period
        )
        _, labelled = label_month(month_dir, rules_path)
        labelled.to_parquet(out / f"labelled_{period}.parquet", index=False)
    return out
