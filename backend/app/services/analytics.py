"""Dashboard numbers, aggregated in PostgreSQL."""

from sqlalchemy import Select, func, select, true
from sqlalchemy.orm import Session

from app.models import Review, Transaction
from app.schemas.analytics import (
    BandCount,
    BreakdownRow,
    RiskDistribution,
    ScoreBin,
    Summary,
    TopAccount,
    TrendPoint,
)
from app.services.reviews import queue_size

BANDS = ("low", "medium", "high", "critical")
HIGH_BANDS = ("high", "critical")
t = Transaction


def _in_period(stmt: Select, period: str | None) -> Select:
    return stmt.where(t.period == period) if period else stmt


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _avg(value) -> float | None:
    return None if value is None else round(float(value), 1)


def _stats():
    """Aggregates shared by trends and breakdowns."""
    return (
        func.count().label("transactions"),
        func.count().filter(t.is_suspicious).label("suspicious"),
        func.avg(t.risk_score).label("avg_risk_score"),
        func.count().filter(t.risk_band.in_(HIGH_BANDS)).label("high_or_critical"),
        func.coalesce(func.sum(t.exposure_usd), 0).label("exposure_usd"),
    )


def summary(db: Session, period: str | None, review_min_score: int) -> Summary:
    row = db.execute(
        _in_period(
            select(
                func.count().label("transactions"),
                func.count().filter(t.is_suspicious).label("suspicious"),
                func.count(t.risk_score).label("scored"),
                func.avg(t.risk_score).label("avg_risk_score"),
                func.count().filter(t.risk_band.in_(HIGH_BANDS)).label("high_or_critical"),
                func.coalesce(func.sum(t.exposure_usd).filter(t.risk_band.in_(HIGH_BANDS)), 0),
            ).select_from(t),
            period,
        )
    ).one()
    bands = dict(
        db.execute(
            _in_period(
                select(t.risk_band, func.count())
                .where(t.risk_band.is_not(None))
                .group_by(t.risk_band),
                period,
            )
        ).all()
    )
    reviews = db.execute(
        _in_period(
            select(Review.status, Review.decision, func.count())
            .join(t, Review.transaction_pk == t.id)
            .group_by(Review.status, Review.decision),
            period,
        )
    ).all()
    counts = {(status, decision): n for status, decision, n in reviews}
    return Summary(
        period=period,
        periods=db.scalars(select(t.period).distinct().order_by(t.period)).all(),
        transactions=row.transactions,
        suspicious=row.suspicious,
        suspicious_rate=_rate(row.suspicious, row.transactions),
        scored=row.scored,
        avg_risk_score=_avg(row.avg_risk_score),
        high_or_critical=row.high_or_critical,
        exposure_usd_at_risk=round(float(row[5]), 2),
        by_band={b: bands.get(b, 0) for b in BANDS},
        review_queue=queue_size(db, review_min_score, period),
        pending_approval=sum(n for (s, _), n in counts.items() if s == "pending"),
        confirmed=counts.get(("approved", "confirmed"), 0),
        false_positive=counts.get(("approved", "false_positive"), 0),
    )


def risk_distribution(db: Session, period: str | None) -> RiskDistribution:
    bucket = func.least(t.risk_score // 10, 9).label("bucket")
    counts = dict(
        db.execute(
            _in_period(
                select(bucket, func.count()).where(t.risk_score.is_not(None)).group_by(bucket),
                period,
            )
        ).all()
    )
    bins = [
        ScoreBin(score_from=b * 10, score_to=100 if b == 9 else b * 10 + 9, count=counts.get(b, 0))
        for b in range(10)
    ]
    total = sum(counts.values())
    band_counts = dict(
        db.execute(
            _in_period(
                select(t.risk_band, func.count())
                .where(t.risk_band.is_not(None))
                .group_by(t.risk_band),
                period,
            )
        ).all()
    )
    bands = [
        BandCount(band=b, count=band_counts.get(b, 0), share=_rate(band_counts.get(b, 0), total))
        for b in BANDS
    ]
    return RiskDistribution(period=period, bins=bins, bands=bands)


def trends(db: Session, granularity: str, period: str | None) -> list[TrendPoint]:
    key = (t.period if granularity == "month" else t.transaction_date).label("bucket")
    stmt = _in_period(
        select(key, *_stats()).where(key.is_not(None)).group_by(key).order_by(key), period
    )
    return [
        TrendPoint(
            bucket=str(r.bucket),
            transactions=r.transactions,
            suspicious=r.suspicious,
            suspicious_rate=_rate(r.suspicious, r.transactions),
            avg_risk_score=_avg(r.avg_risk_score),
            high_or_critical=r.high_or_critical,
        )
        for r in db.execute(stmt)
    ]


DIMENSIONS = {
    "currency": t.currency,
    "country": t.country,
    "description": t.description,
    "period": t.period,
    "band": t.risk_band,
}


def breakdown(db: Session, by: str, period: str | None, limit: int) -> list[BreakdownRow]:
    if by == "break_type":
        breaks = func.jsonb_array_elements_text(t.break_types).table_valued("value").lateral("bt")
        key = breaks.c.value.label("key")
        stmt = select(key, *_stats()).select_from(t).join(breaks, true())
    else:
        key = DIMENSIONS[by].label("key")
        stmt = select(key, *_stats()).select_from(t)
    stmt = _in_period(stmt, period).group_by(key)
    stmt = stmt.order_by(func.count().filter(t.is_suspicious).desc(), key).limit(limit)
    return [
        BreakdownRow(
            key=r.key,
            transactions=r.transactions,
            suspicious=r.suspicious,
            suspicious_rate=_rate(r.suspicious, r.transactions),
            avg_risk_score=_avg(r.avg_risk_score),
            high_or_critical=r.high_or_critical,
            exposure_usd=round(float(r.exposure_usd), 2),
        )
        for r in db.execute(stmt)
    ]


def top_accounts(db: Session, period: str | None, limit: int) -> list[TopAccount]:
    suspicious = func.count().filter(t.is_suspicious)
    exposure = func.coalesce(func.sum(t.exposure_usd).filter(t.is_suspicious), 0)
    stmt = _in_period(
        select(
            t.gl_account_id,
            func.count().label("transactions"),
            suspicious.label("suspicious"),
            func.max(t.risk_score).label("max_risk_score"),
            exposure.label("exposure_usd"),
            func.max(t.transaction_date).label("last_date"),
        )
        .where(t.gl_account_id.is_not(None))
        .group_by(t.gl_account_id)
        .having(suspicious > 0),
        period,
    ).order_by(suspicious.desc(), exposure.desc(), t.gl_account_id)
    return [
        TopAccount(
            account=r.gl_account_id,
            transactions=r.transactions,
            suspicious=r.suspicious,
            max_risk_score=r.max_risk_score,
            exposure_usd=round(float(r.exposure_usd), 2),
            last_transaction_date=r.last_date.isoformat() if r.last_date else None,
        )
        for r in db.execute(stmt.limit(limit))
    ]
