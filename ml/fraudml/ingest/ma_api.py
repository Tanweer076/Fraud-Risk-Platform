"""Management Accounting reader.

MA data is served by a paginated REST API (`GET /api/ma/transactions`). For offline runs and
CI, `read_ma_embedded` decodes the compressed payload stored in the month's server script
without executing it. `read_ma_file` also accepts CSV or JSON exports of the API data.
"""

import base64
import io
import json
import re
import zlib
from pathlib import Path

import httpx
import pandas as pd

from fraudml.canonical.normalise import to_canonical
from fraudml.errors import IngestionError

MAX_PER_PAGE = 5000


def read_ma_api(
    base_url: str,
    *,
    per_page: int = MAX_PER_PAGE,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    owns_client = client is None
    client = client or httpx.Client(base_url=base_url, timeout=timeout)
    rows: list[dict] = []
    try:
        page, total_pages = 1, 1
        while page <= total_pages:
            resp = client.get("/api/ma/transactions", params={"page": page, "per_page": per_page})
            if resp.status_code != 200:
                raise IngestionError(
                    f"MA API returned {resp.status_code} for page {page}: {resp.text[:200]}"
                )
            body = resp.json()
            rows.extend(body["data"])
            total_pages = body["total_pages"]
            page += 1
    except httpx.HTTPError as exc:
        raise IngestionError(f"MA API request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    if not rows:
        raise IngestionError("MA API returned no transactions")
    return to_canonical(pd.DataFrame(rows), "ma")


_DATA_PATTERN = re.compile(r'^_DATA\s*=\s*"([A-Za-z0-9+/=]+)"', re.MULTILINE)


def read_ma_embedded(path: str | Path) -> pd.DataFrame:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"Cannot read MA server script {path}: {exc}") from exc

    match = _DATA_PATTERN.search(source)
    if not match:
        raise IngestionError(f"No embedded MA payload found in {path}")
    try:
        csv_text = zlib.decompress(base64.b64decode(match.group(1))).decode("utf-8")
    except (ValueError, zlib.error) as exc:
        raise IngestionError(f"Embedded MA payload in {path} is corrupt: {exc}") from exc

    raw = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    return to_canonical(raw, "ma")


def read_ma_file(path: str | Path) -> pd.DataFrame:
    """Read MA data from a server script (.py), a CSV export or a JSON export.

    JSON may be a list of records or an API page ({"data": [...]}).
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".py":
        return read_ma_embedded(path)
    try:
        if suffix == ".csv":
            raw = pd.read_csv(path, dtype=str, keep_default_na=False)
        elif suffix == ".json":
            body = json.loads(path.read_text(encoding="utf-8"))
            rows = body.get("data") if isinstance(body, dict) else body
            if not isinstance(rows, list):
                raise IngestionError(f"MA JSON {path} must be a list or have a 'data' list")
            raw = pd.DataFrame(rows).astype("string")
        else:
            raise IngestionError(f"Unsupported MA file type {suffix!r}; use .py, .csv or .json")
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise IngestionError(f"Cannot read MA file {path}: {exc}") from exc
    if raw.empty:
        raise IngestionError(f"MA file {path} has no transactions")
    return to_canonical(raw, "ma")
