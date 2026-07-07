"""Prometheus metrics for retention, on the shared idempotent factory."""

from __future__ import annotations

import time

from smarthr360_integration.observability import get_counter, get_gauge

ATTRITION_PREDICTIONS = get_counter(
    "retention_attrition_predictions_total",
    "Attrition predictions produced, by risk level.",
    ["level"],
)

ATTRITION_HIGH_RISK = get_gauge(
    "retention_attrition_high_risk_employees",
    "Employees currently at HIGH or CRITICAL attrition risk (latest run).",
)

ATTRITION_LAST_RUN = get_gauge(
    "retention_attrition_last_run_timestamp_seconds",
    "Unix time of the last attrition prediction run.",
)


def record_prediction(level: str) -> None:
    try:
        ATTRITION_PREDICTIONS.labels(level=level).inc()
    except Exception:  # pragma: no cover
        pass


def set_high_risk_count(count: int) -> None:
    try:
        ATTRITION_HIGH_RISK.set(count)
        ATTRITION_LAST_RUN.set(time.time())
    except Exception:  # pragma: no cover
        pass
