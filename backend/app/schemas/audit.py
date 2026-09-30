from datetime import datetime

from app.schemas.common import ORMModel


class AuditOut(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    before: dict | None
    after: dict | None
    request_id: str | None
    created_at: datetime
