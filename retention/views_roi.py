"""Cost-of-attrition / ROI view — turns risk into money (HR).

Closes the retention loop by pairing:
  * forward-looking € exposure from the latest attrition forecast, and
  * realized savings from actions whose outcome was recorded
    (``employee_retained``).

Replacement/action costs are assumptions (HR configures them; sensible defaults
+ query-param overrides) since the ERP holds the real compensation figures.
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .models import Action, AttritionForecast

AT_RISK_LEVELS = {"HIGH", "CRITICAL"}


class RetentionROIView(APIView):
    """GET /api/retention/roi/ — attrition cost exposure and retention ROI."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_hr_access(request.user):
            raise PermissionDenied("HR or Admin role required.")

        def _num(name, default):
            try:
                return float(request.query_params.get(name, default))
            except (TypeError, ValueError):
                return default

        replacement_cost = _num("avg_replacement_cost", 45000)
        action_cost = _num("action_cost", 5000)
        effectiveness = min(max(_num("action_effectiveness", 0.4), 0.0), 1.0)

        latest = AttritionForecast.objects.order_by("-generated_at").first()
        forecasts = (
            list(AttritionForecast.objects.filter(run_id=latest.run_id)) if latest else []
        )

        by_level: dict[str, dict] = {}
        total_exposure = 0.0
        at_risk_exposure = 0.0
        at_risk_count = 0
        for f in forecasts:
            exposure = (f.risk_score / 100.0) * replacement_cost
            total_exposure += exposure
            row = by_level.setdefault(f.level, {"level": f.level, "count": 0, "exposure": 0.0})
            row["count"] += 1
            row["exposure"] += exposure
            if f.level in AT_RISK_LEVELS:
                at_risk_exposure += exposure
                at_risk_count += 1

        # Acting on the at-risk group: avoid `effectiveness` share of their
        # expected loss, net of the cost of one action per person.
        potential_savings = at_risk_exposure * effectiveness - action_cost * at_risk_count

        # Realized (closed loop): actions with a recorded outcome.
        acted = Action.objects.filter(employee_retained__isnull=False)
        acted_total = acted.count()
        retained = acted.filter(employee_retained=True).count()
        realized_savings = retained * (replacement_cost - action_cost)
        retention_rate = round(retained / acted_total, 3) if acted_total else None

        for row in by_level.values():
            row["exposure"] = round(row["exposure"])

        return Response(
            {
                "assumptions": {
                    "avg_replacement_cost": replacement_cost,
                    "action_cost": action_cost,
                    "action_effectiveness": effectiveness,
                },
                "forward": {
                    "total_exposure": round(total_exposure),
                    "at_risk_count": at_risk_count,
                    "at_risk_exposure": round(at_risk_exposure),
                    "potential_savings": round(potential_savings),
                    "by_level": sorted(by_level.values(), key=lambda r: r["exposure"], reverse=True),
                },
                "realized": {
                    "actions_with_outcome": acted_total,
                    "retained": retained,
                    "retention_rate": retention_rate,
                    "realized_savings": round(realized_savings),
                },
            }
        )
