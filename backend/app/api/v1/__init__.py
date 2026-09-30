from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    audit,
    auth,
    health,
    ingestion,
    models,
    predictions,
    reports,
    reviews,
    transactions,
    users,
)

api_router = APIRouter()
for module in (
    health,
    auth,
    users,
    predictions,
    transactions,
    ingestion,
    analytics,
    models,
    reviews,
    reports,
    audit,
):
    api_router.include_router(module.router)
