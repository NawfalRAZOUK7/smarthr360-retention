"""Forward-looking attrition prediction.

Distinct from ``detection.RiskDetectionService`` (which flags *current* risk from
static thresholds): this projects an employee's likelihood of leaving using the
*trajectory* of their risk signals plus engagement / performance / absence.

The analytic core (:func:`score_attrition`) is pure — it takes plain values and
a list of (days_ago, intensity) signal points — so it unit-tests without a DB.
Trend uses the shared least-squares helper (smarthr360-integration.analytics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from smarthr360_integration.analytics import clamp, linear_trend

# Weights of each driver in the composite risk (sum = 1.0).
WEIGHTS = {
    "engagement": 0.30,
    "performance": 0.15,
    "absence": 0.15,
    "signal_pressure": 0.25,
    "trend": 0.15,
}
ABSENCE_CAP_DAYS = 30.0


@dataclass
class AttritionFactors:
    engagement: float
    performance: float
    absence: float
    signal_pressure: float
    trend: float


@dataclass
class AttritionResult:
    risk_score: float          # 0..100
    level: str                 # LOW | MEDIUM | HIGH | CRITICAL
    factors: AttritionFactors
    signal_trend_per_day: float
    top_drivers: list = field(default_factory=list)
    rationale: str = ""

    def as_dict(self) -> dict:
        return {
            "risk_score": round(self.risk_score, 1),
            "level": self.level,
            "factors": {
                "engagement": round(self.factors.engagement, 3),
                "performance": round(self.factors.performance, 3),
                "absence": round(self.factors.absence, 3),
                "signal_pressure": round(self.factors.signal_pressure, 3),
                "trend": round(self.factors.trend, 3),
            },
            "signal_trend_per_day": round(self.signal_trend_per_day, 3),
            "top_drivers": self.top_drivers,
            "rationale": self.rationale,
        }


def _level(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def score_attrition(
    *,
    engagement_score: float,
    performance_score: float,
    absence_days_90d: float,
    unresolved_signal_intensities: Sequence[float],
    signal_points: Sequence[tuple[float, float]] = (),
) -> AttritionResult:
    """Composite attrition risk in 0..100.

    ``signal_points`` are (days_ago, intensity) — a *rising* recent intensity
    (negative slope vs days_ago, i.e. more intense as days_ago -> 0) increases
    risk. We pass points as (x=-days_ago, y=intensity) so a positive slope means
    worsening over time.
    """
    engagement = clamp((100.0 - engagement_score) / 100.0, 0.0, 1.0)
    performance = clamp((100.0 - performance_score) / 100.0, 0.0, 1.0)
    absence = clamp(absence_days_90d / ABSENCE_CAP_DAYS, 0.0, 1.0)

    if unresolved_signal_intensities:
        signal_pressure = clamp(
            sum(unresolved_signal_intensities)
            / (100.0 * len(unresolved_signal_intensities))
            * min(1.0 + 0.15 * (len(unresolved_signal_intensities) - 1), 1.6),
            0.0,
            1.0,
        )
    else:
        signal_pressure = 0.0

    slope = linear_trend([(-d, i) for d, i in signal_points]) if signal_points else 0.0
    # Normalise slope (intensity/day) into 0..1; ~2/day of worsening = full.
    trend = clamp(slope / 2.0, 0.0, 1.0)

    factors = AttritionFactors(
        engagement, performance, absence, signal_pressure, trend
    )
    risk = 100.0 * (
        WEIGHTS["engagement"] * engagement
        + WEIGHTS["performance"] * performance
        + WEIGHTS["absence"] * absence
        + WEIGHTS["signal_pressure"] * signal_pressure
        + WEIGHTS["trend"] * trend
    )
    risk = clamp(risk, 0.0, 100.0)

    contributions = {
        "low engagement": WEIGHTS["engagement"] * engagement,
        "poor performance": WEIGHTS["performance"] * performance,
        "high absence": WEIGHTS["absence"] * absence,
        "active risk signals": WEIGHTS["signal_pressure"] * signal_pressure,
        "worsening trend": WEIGHTS["trend"] * trend,
    }
    top = [k for k, _ in sorted(contributions.items(), key=lambda kv: -kv[1]) if _ > 0][:3]

    rationale = (
        f"Attrition risk {risk:.0f}/100 ({_level(risk)}). "
        + ("Main drivers: " + ", ".join(top) + "." if top else "No material drivers.")
    )
    return AttritionResult(
        risk_score=risk,
        level=_level(risk),
        factors=factors,
        signal_trend_per_day=slope,
        top_drivers=top,
        rationale=rationale,
    )
