from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import DB, AppSettings, CurrentUser
from app.schemas.analytics import (
    BreakdownBy,
    BreakdownRow,
    RiskDistribution,
    Summary,
    TopAccount,
    TrendPoint,
)
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])

Period = Annotated[str | None, Query(pattern=r"^\d{6}$", description="YYYYMM; all if omitted")]


@router.get("/summary", response_model=Summary)
def summary(db: DB, settings: AppSettings, _: CurrentUser, period: Period = None):
    """KPIs: volumes, suspicious rate, average score, bands, USD at risk and review counts."""
    return analytics.summary(db, period, settings.review_min_score)


@router.get("/risk-distribution", response_model=RiskDistribution)
def risk_distribution(db: DB, _: CurrentUser, period: Period = None):
    return analytics.risk_distribution(db, period)


@router.get("/trends", response_model=list[TrendPoint])
def trends(
    db: DB,
    _: CurrentUser,
    granularity: Literal["day", "month"] = "day",
    period: Period = None,
):
    return analytics.trends(db, granularity, period)


@router.get("/breakdown", response_model=list[BreakdownRow])
def breakdown(
    db: DB,
    _: CurrentUser,
    by: BreakdownBy,
    period: Period = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return analytics.breakdown(db, by, period, limit)


@router.get("/top-accounts", response_model=list[TopAccount])
def top_accounts(
    db: DB, _: CurrentUser, period: Period = None, limit: Annotated[int, Query(ge=1, le=100)] = 10
):
    """GL accounts with the most suspicious transactions, then the most USD at stake."""
    return analytics.top_accounts(db, period, limit)
