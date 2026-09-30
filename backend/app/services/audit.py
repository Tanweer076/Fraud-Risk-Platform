from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.logging import request_id_var
from app.ml.registry import json_safe
from app.models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    entity: str,
    entity_id: object = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Add an audit entry to the session; it is committed with the change it describes."""
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=None if entity_id is None else str(entity_id),
            before=json_safe(jsonable_encoder(before)) if before is not None else None,
            after=json_safe(jsonable_encoder(after)) if after is not None else None,
            request_id=request_id_var.get(),
        )
    )
