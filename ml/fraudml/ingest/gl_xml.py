"""General Ledger reader: XML report with one <Transaction> element per record."""

from pathlib import Path
from xml.etree.ElementTree import ParseError

import pandas as pd
from defusedxml import ElementTree

from fraudml.canonical.normalise import to_canonical
from fraudml.errors import IngestionError


def read_gl_xml(path: str | Path) -> pd.DataFrame:
    try:
        root = ElementTree.parse(str(path)).getroot()
    except (ParseError, OSError) as exc:
        raise IngestionError(f"Cannot read GL XML {path}: {exc}") from exc

    rows = [{child.tag: child.text for child in txn} for txn in root.iter("Transaction")]
    if not rows:
        raise IngestionError(f"GL XML {path} has no <Transaction> elements")
    return to_canonical(pd.DataFrame(rows), "gl")
