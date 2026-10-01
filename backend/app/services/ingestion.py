"""Load a month of GL, MA and FA records: read, link, label, score and store.

Uploads are saved to UPLOAD_DIR and processed in the background. The batch row records how MA
arrived (file, REST API or CLI), how many records each source had, how long it took and the
outcome, as the use case asks. Nothing from a failed batch is kept except the failed batch row.
"""

import logging
import re
import shutil
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
from fastapi import UploadFile
from fraudml.errors import IngestionError
from fraudml.ingest.fa_csv import read_fa_csv
from fraudml.ingest.gl_xml import read_gl_xml
from fraudml.ingest.join_map import read_join_map
from fraudml.ingest.ma_api import read_ma_api, read_ma_file
from fraudml.ingest.rules import Rule
from fraudml.labels.break_labeller import summarise
from fraudml.pipeline import label_records
from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core import metrics
from app.core.config import Settings
from app.core.errors import AppError, BadRequest, NotFound, Unavailable
from app.ml.frames import transaction_values
from app.ml.registry import LoadedModel, ModelRegistry
from app.models import AccountKeyMap, IngestionBatch, Prediction, Transaction, User
from app.repositories import transactions as repo
from app.services import audit
from app.services.scoring import prediction_values, score_fields

log = logging.getLogger(__name__)

SOURCES = ("gl", "ma", "fa", "join_map")
SUFFIXES = {
    "gl": {".xml"},
    "ma": {".py", ".csv", ".json"},
    "fa": {".csv"},
    "join_map": {".txt", ".csv"},
}
PERIOD_PATTERN = r"^\d{4}(0[1-9]|1[0-2])$"
CHUNK_ROWS = 1000
SCORE_COLUMNS = (
    "risk_score",
    "risk_band",
    "priority",
    "exposure_usd",
    "probability",
    "model_version",
    "scored_at",
)
# Kept from the stored row when a reload updates a transaction.
KEEP_ON_RELOAD = {"transaction_id", "created_at", "created_by_id", "review_outcome"}


class UploadTooLarge(AppError):
    status_code = 413


# --- validation and upload handling -----------------------------------------------------------


def check_suffix(source: str, filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUFFIXES[source]:
        allowed = ", ".join(sorted(SUFFIXES[source]))
        raise BadRequest(f"The {source} file must be one of: {allowed} (got {filename!r})")
    return suffix


def check_ma_url(url: str, allowed_hosts: list[str]) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BadRequest("ma_url must be an http(s) URL")
    if parts.username or parts.password:
        raise BadRequest("ma_url must not contain credentials")
    if parts.hostname.lower() not in {h.lower() for h in allowed_hosts}:
        raise BadRequest(
            f"Pulling MA from {parts.hostname} is not allowed; ask an admin to add it to "
            "MA_API_ALLOWED_HOSTS"
        )
    return url


def save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> Path:
    written = 0
    with dest.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                raise UploadTooLarge(f"{upload.filename} is larger than {max_bytes // 2**20} MB")
            out.write(chunk)
    return dest


def create_batch(
    db: Session, period: str, method: str, files: dict, user: User | None
) -> IngestionBatch:
    batch = IngestionBatch(period=period, method=method, status="queued", files=files)
    batch.created_by_id = user.id if user else None
    db.add(batch)
    db.flush()
    audit.record(db, user, "ingestion.create", "ingestion_batch", batch.id, after=files)
    db.commit()
    return batch


def store_uploads(
    batch: IngestionBatch, uploads: dict[str, UploadFile], settings: Settings
) -> dict[str, Path]:
    """Save the uploaded files under UPLOAD_DIR/batch_<id>/ with fixed names."""
    folder = Path(settings.upload_dir) / f"batch_{batch.id}"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        return {
            source: save_upload(
                upload,
                folder / f"{source}{check_suffix(source, upload.filename)}",
                settings.max_upload_mb * 2**20,
            )
            for source, upload in uploads.items()
        }
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def find_month_files(month_dir: Path) -> tuple[str, dict[str, Path]]:
    """The period and source files of a month folder laid out like the OneRecon dataset."""
    patterns = {
        "gl": "gl_report_*.xml",
        "ma": "ma_api_server_*.py",
        "fa": "fa_report_*.csv",
        "join_map": "join_map.txt",
    }
    paths = {}
    for source, pattern in patterns.items():
        matches = sorted(Path(month_dir).glob(pattern))
        if len(matches) != 1:
            raise IngestionError(f"Expected one {pattern} in {month_dir}, found {len(matches)}")
        paths[source] = matches[0]
    period = re.search(r"(\d{6})", paths["gl"].name)
    if period is None:
        raise IngestionError(f"No YYYYMM period in {paths['gl'].name}")
    return period.group(1), paths


# --- the batch job ----------------------------------------------------------------------------


def run_batch(
    make_session: sessionmaker,
    registry: ModelRegistry,
    rules: list[Rule],
    settings: Settings,
    batch_id: int,
    paths: dict[str, Path],
    ma_url: str | None = None,
) -> None:
    """Process one batch. Runs in the background, so it records failures instead of raising."""
    with make_session() as db:
        batch = db.get(IngestionBatch, batch_id)
        batch.status, batch.started_at = "running", datetime.now(UTC)
        db.commit()
        started = time.perf_counter()
        try:
            _load(db, registry, rules, settings, batch, paths, ma_url)
            batch.status = "succeeded"
        except Exception as exc:
            db.rollback()
            log.exception("Ingestion batch %s failed", batch_id)
            batch = db.get(IngestionBatch, batch_id)
            batch.status = "failed"
            batch.error = _describe(exc)
        batch.duration_ms = int((time.perf_counter() - started) * 1000)
        batch.finished_at = datetime.now(UTC)
        db.commit()
        log.info("Ingestion batch %s %s in %d ms", batch_id, batch.status, batch.duration_ms or 0)
        _record_metrics(db, batch)


def _record_metrics(db: Session, batch: IngestionBatch) -> None:
    metrics.BATCHES.labels(batch.status).inc()
    metrics.BATCH_DURATION.observe((batch.duration_ms or 0) / 1000)
    if batch.status != "succeeded":
        return
    scored = db.execute(
        select(Transaction.risk_band, Transaction.risk_score).where(
            Transaction.batch_id == batch.id,
            Transaction.scored_at >= batch.started_at,
            Transaction.risk_score.is_not(None),
        )
    ).all()
    bands = Counter(band for band, _ in scored)
    metrics.record_scores("batch", bands, [score for _, score in scored])


def _describe(exc: Exception) -> str:
    if isinstance(exc, (IngestionError, ValueError, AppError)):
        text = str(exc)
    else:
        text = f"{type(exc).__name__}: {exc}"
    return text[:2000]


def _load(
    db: Session,
    registry: ModelRegistry,
    rules: list[Rule],
    settings: Settings,
    batch: IngestionBatch,
    paths: dict[str, Path],
    ma_url: str | None,
) -> None:
    period = batch.period
    records = {
        "gl": read_gl_xml(paths["gl"]),
        "ma": read_ma_api(ma_url) if ma_url else read_ma_file(paths["ma"]),
        "fa": read_fa_csv(paths["fa"]),
    }
    join_map = read_join_map(paths["join_map"])
    batch.records = {s: len(df) for s, df in records.items()} | {"join_map": len(join_map)}

    labelled = label_records(records, join_map, rules, period)
    labelled["period"] = period

    try:
        model = registry.current(db)
    except Unavailable:
        model = None
    scored = None
    if model is not None:
        accounts = labelled["account_key_gl"].dropna().unique().tolist()
        history = repo.period_history(db, before=period, accounts=accounts)
        scored = model.scorer.score(
            labelled, history=history, explain_min_score=settings.explain_min_score
        )

    _replace_join_map(db, period, join_map, batch.id)
    ids = _upsert_transactions(db, labelled, scored, model, batch)
    if scored is not None:
        _insert_predictions(db, scored, ids, model)

    batch.transactions_loaded = len(labelled)
    batch.transactions_scored = 0 if scored is None else len(scored)
    summary = summarise(labelled)
    if scored is None:
        summary["note"] = "Not scored: no active model"
    else:
        summary["bands"] = {k: int(v) for k, v in scored["band"].value_counts().items()}
        summary["model_version"] = model.version
    batch.summary = summary


def _chunks(rows: list, size: int = CHUNK_ROWS) -> Iterator[list]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _replace_join_map(db: Session, period: str, join_map: pd.DataFrame, batch_id: int) -> None:
    db.execute(delete(AccountKeyMap).where(AccountKeyMap.period == period))
    rows = [
        {
            "period": period,
            "gl_account_id": r.gl_account_id,
            "ma_customer_key": r.ma_customer_key,
            "fa_key": r.fa_key,
            "entity": r.entity or None,
            "effective_from": r.effective_from.date(),
            "effective_to": r.effective_to.date(),
            "batch_id": batch_id,
        }
        for r in join_map.itertuples(index=False)
    ]
    if rows:
        db.execute(insert(AccountKeyMap.__table__), rows)


def _upsert_transactions(
    db: Session,
    labelled: pd.DataFrame,
    scored: pd.DataFrame | None,
    model: LoadedModel | None,
    batch: IngestionBatch,
) -> dict[str, int]:
    """Insert or update every transaction; returns TransactionID -> primary key."""
    scored_at = datetime.now(UTC)
    scores = scored.to_dict("records") if scored is not None else [None] * len(labelled)
    rows = []
    for row, score in zip(labelled.to_dict("records"), scores, strict=True):
        values = transaction_values(row) | {
            "period": batch.period,
            "source": "batch",
            "batch_id": batch.id,
        }
        if score is None:
            values |= dict.fromkeys(SCORE_COLUMNS)
        else:
            values |= score_fields(score, model, scored_at)
        rows.append(values)

    # One statement run for many parameter sets: SQLAlchemy batches it into multi-row INSERTs
    # without recompiling, which is far faster than building one huge VALUES list per chunk.
    table = Transaction.__table__
    stmt = pg_insert(table)
    updates = {c: stmt.excluded[c] for c in rows[0] if c not in KEEP_ON_RELOAD} if rows else {}
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.transaction_id], set_={**updates, "updated_at": func.now()}
    )
    for chunk in _chunks(rows, 5000):
        db.execute(stmt, chunk)
    return dict(
        db.execute(
            select(Transaction.transaction_id, Transaction.id).where(
                Transaction.batch_id == batch.id
            )
        ).all()
    )


def _insert_predictions(
    db: Session, scored: pd.DataFrame, ids: dict[str, int], model: LoadedModel
) -> None:
    rows = [
        {"transaction_pk": ids[str(r["transaction_id"])], **prediction_values(r, model, "batch")}
        for r in scored.to_dict("records")
    ]
    for chunk in _chunks(rows, 5000):
        db.execute(insert(Prediction.__table__), chunk)


# --- queries ----------------------------------------------------------------------------------


def get_batch(db: Session, batch_id: int) -> IngestionBatch:
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise NotFound(f"Ingestion batch {batch_id} not found")
    return batch


def list_batches(db: Session, page: int, page_size: int) -> tuple[list[IngestionBatch], int]:
    stmt = select(IngestionBatch).order_by(IngestionBatch.id.desc())
    total = db.scalar(select(func.count()).select_from(IngestionBatch)) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total
