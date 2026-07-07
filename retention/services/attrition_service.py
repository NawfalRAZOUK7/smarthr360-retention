"""Attrition prediction orchestration (ORM data access).

Builds inputs from Employee + Signal history, calls the pure
:func:`score_attrition`, snapshots the risk band (shared SCD2) and emits
Prometheus gauges. Returns/persists AttritionForecast rows for BI.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from smarthr360_integration.history import snapshot_history

from ..metrics import record_prediction, set_high_risk_count
from ..models import AttritionForecast, AttritionRiskHistory, Employee, Signal
from .attrition import score_attrition

logger = logging.getLogger("retention.attrition")


class AttritionEngine:
    def __init__(self, *, lookback_days: int = 90):
        self.lookback_days = lookback_days

    def run(self, *, persist: bool = True):
        run_id = uuid4().hex
        now = timezone.now()
        results = []
        high = 0

        for emp in Employee.objects.all():
            result = self._predict_one(emp, now)
            record_prediction(result.level)
            if result.level in ("HIGH", "CRITICAL"):
                high += 1

            # SCD2: track the risk-band dwell time (idempotent, shared service).
            snapshot_history(
                AttritionRiskHistory,
                owner_filter={"employee_pk": emp.pk},
                snapshot={"level": result.level},
                source_system="RETENTION",
            )

            row = {
                "employee_id": emp.employee_id,
                "employee_pk": emp.pk,
                "name": emp.name,
                **result.as_dict(),
            }
            results.append((emp, result, row))

        set_high_risk_count(high)

        if persist:
            AttritionForecast.objects.bulk_create(
                [
                    AttritionForecast(
                        employee=emp,
                        risk_score=res.risk_score,
                        level=res.level,
                        factors=res.as_dict()["factors"],
                        signal_trend_per_day=res.signal_trend_per_day,
                        top_drivers=res.top_drivers,
                        rationale=res.rationale,
                        run_id=run_id,
                    )
                    for emp, res, _ in results
                ]
            )

        payload = [r for _, _, r in results]
        payload.sort(key=lambda r: r["risk_score"], reverse=True)
        logger.info("attrition run %s: %d employees, %d high/critical", run_id, len(payload), high)
        return run_id, payload

    def predict_employee(self, employee: Employee) -> dict:
        res = self._predict_one(employee, timezone.now())
        record_prediction(res.level)
        return {"employee_id": employee.employee_id, "name": employee.name, **res.as_dict()}

    # ------------------------------------------------------------------
    def _predict_one(self, emp: Employee, now):
        since = now - timedelta(days=self.lookback_days)
        signals = list(
            Signal.objects.filter(employee=emp, detected_at__gte=since)
            .order_by("detected_at")
            .values_list("detected_at", "intensity", "resolved")
        )
        unresolved = [float(i) for _, i, resolved in signals if not resolved]
        points = [
            ((now - dt).total_seconds() / 86400.0, float(i)) for dt, i, _ in signals
        ]
        return score_attrition(
            engagement_score=emp.engagement_score,
            performance_score=emp.performance_score,
            absence_days_90d=emp.absence_days_90d,
            unresolved_signal_intensities=unresolved,
            signal_points=points,
        )
