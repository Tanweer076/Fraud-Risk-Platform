from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Request, UploadFile, status

from app.api.deps import DB, AppSettings, CurrentUser, Limiter, Maker, Registry, Rules
from app.core.errors import BadRequest
from app.schemas.common import Page
from app.schemas.ingestion import BatchOut
from app.services import ingestion

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/upload", response_model=BatchOut, status_code=status.HTTP_202_ACCEPTED)
def upload_month(
    request: Request,
    background: BackgroundTasks,
    db: DB,
    settings: AppSettings,
    registry: Registry,
    rules: Rules,
    user: Maker,
    limiter: Limiter,
    period: Annotated[str, Form(pattern=ingestion.PERIOD_PATTERN, examples=["202608"])],
    gl: Annotated[UploadFile, File(description="GL report (.xml)")],
    fa: Annotated[UploadFile, File(description="FA report (.csv)")],
    join_map: Annotated[UploadFile, File(description="Join map (.txt or .csv)")],
    ma: Annotated[
        UploadFile | None, File(description="MA server script (.py) or export (.csv, .json)")
    ] = None,
    ma_url: Annotated[
        str | None, Form(description="Pull MA from its REST API instead of a file")
    ] = None,
):
    """Load a month: GL, FA and join map files, plus MA as a file or from its REST API.

    Returns at once with a queued batch; poll GET /ingestion/batches/{id} for the outcome.
    """
    limiter.hit("upload", f"user:{user.id}")
    if (ma is None) == (ma_url is None):
        raise BadRequest("Send either an MA file or ma_url, not both or neither")
    uploads = {"gl": gl, "fa": fa, "join_map": join_map} | ({"ma": ma} if ma else {})
    for source, upload in uploads.items():
        ingestion.check_suffix(source, upload.filename)
    if ma_url:
        ingestion.check_ma_url(ma_url, settings.ma_api_allowed_hosts)

    files = {source: upload.filename for source, upload in uploads.items()}
    if ma_url:
        files["ma"] = ma_url
    batch = ingestion.create_batch(db, period, "api" if ma_url else "file", files, user)
    try:
        paths = ingestion.store_uploads(batch, uploads, settings)
    except Exception as exc:
        batch.status, batch.error = "failed", str(exc)[:2000]
        db.commit()
        raise
    background.add_task(
        ingestion.run_batch,
        request.app.state.sessionmaker,
        registry,
        rules,
        settings,
        batch.id,
        paths,
        ma_url,
    )
    return batch


@router.get("/batches", response_model=Page[BatchOut])
def list_batches(
    db: DB,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
):
    items, total = ingestion.list_batches(db, page, page_size)
    return Page[BatchOut](items=items, total=total, page=page, page_size=page_size)


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: int, db: DB, _: CurrentUser):
    return ingestion.get_batch(db, batch_id)
