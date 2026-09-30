from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB, AuditReader
from app.models import AuditLog
from app.schemas.audit import AuditOut
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditOut])
def list_audit(
    db: DB,
    _: AuditReader,
    entity: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """The audit trail, newest first."""
    conditions = []
    if entity:
        conditions.append(AuditLog.entity == entity)
    if entity_id:
        conditions.append(AuditLog.entity_id == entity_id)
    if action:
        conditions.append(AuditLog.action == action)
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    items = db.scalars(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page[AuditOut](items=items, total=total, page=page, page_size=page_size)
