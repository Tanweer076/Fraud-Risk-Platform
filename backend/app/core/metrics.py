"""Prometheus metrics, served at /metrics.

With several API worker processes, set PROMETHEUS_MULTIPROC_DIR to an empty folder before they
start (the Docker image does): each process then writes its values there and /metrics adds
them up. Without it, /metrics reports the one process that answers.
"""

import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    disable_created_metrics,
    generate_latest,
    multiprocess,
)

# The *_created series only add noise for Prometheus, which tracks resets itself.
disable_created_metrics()

LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
SCORE_BUCKETS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests answered", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Time to answer an HTTP request",
    ["method", "route"],
    buckets=LATENCY_BUCKETS,
)
SCORED = Counter(
    "fraud_scored_transactions_total",
    "Transactions scored, by where they came from (api or batch) and risk band",
    ["source", "band"],
)
RISK_SCORE = Histogram(
    "fraud_risk_score",
    "Risk scores given, for watching the score distribution drift",
    ["source"],
    buckets=SCORE_BUCKETS,
)
SCORING_LATENCY = Histogram(
    "fraud_scoring_duration_seconds",
    "Time to score and store one submitted transaction",
    buckets=LATENCY_BUCKETS,
)
BATCHES = Counter("fraud_ingestion_batches_total", "Month loads finished", ["status"])
BATCH_DURATION = Histogram(
    "fraud_ingestion_duration_seconds",
    "Time to load and score a month",
    buckets=(1, 5, 10, 20, 30, 60, 120, 300, 600),
)
REVIEW_FINDINGS = Counter(
    "fraud_review_findings_total",
    "Findings recorded by analysts (confirmed or false_positive)",
    ["decision"],
)
REVIEW_DECISIONS = Counter(
    "fraud_review_decisions_total",
    "Approvers' decisions on findings; approved ones by finding are the live precision signal",
    ["status", "decision"],
)
RATE_LIMITED = Counter("fraud_rate_limited_total", "Requests refused by a rate limit", ["scope"])
ACTIVE_MODEL = Gauge(
    "fraud_active_model_info",
    "1 for the model version the API scores with",
    ["version"],
    multiprocess_mode="max",
)


def set_active_model(version: str, previous: str | None) -> None:
    if previous and previous != version:
        ACTIVE_MODEL.labels(previous).set(0)
    ACTIVE_MODEL.labels(version).set(1)


def record_scores(source: str, bands: dict[str, int], scores=()) -> None:
    """Count scored transactions per band, and add their risk scores to the histogram."""
    for band, count in bands.items():
        if count:
            SCORED.labels(source, band).inc(count)
    histogram = RISK_SCORE.labels(source)
    for score in scores:
        histogram.observe(score)


def render() -> tuple[bytes, str]:
    """The metrics page and its content type."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    return generate_latest(registry), CONTENT_TYPE_LATEST
