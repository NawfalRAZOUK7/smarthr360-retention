"""Attrition prediction endpoint (Phase 2 feature, HR only).

    GET /api/retention/attrition/                  predict for all employees
    GET /api/retention/attrition/?employee_id=E42   one employee

Forward-looking, distinct from /detect/ (current-state) and /outcomes/
(effectiveness). Ranked by risk.
"""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_integration.api import not_found
from smarthr360_jwt_auth.access import has_hr_access

from .models import Employee
from .services.attrition_service import AttritionEngine


class AttritionForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_hr_access(request.user):
            from smarthr360_integration.api import forbidden

            return forbidden("HR or Admin role required.")

        engine = AttritionEngine()
        employee_id = request.query_params.get("employee_id")

        if employee_id:
            emp = Employee.objects.filter(employee_id=employee_id).first()
            if emp is None:
                return not_found(
                    "employee_not_found", f"Unknown employee_id '{employee_id}'."
                )
            return Response(
                {"data": engine.predict_employee(emp), "meta": {"success": True}}
            )

        persist = str(request.query_params.get("persist", "false")).lower() in {
            "true",
            "1",
        }
        run_id, forecasts = engine.run(persist=persist)
        summary = {
            "critical": sum(1 for f in forecasts if f["level"] == "CRITICAL"),
            "high": sum(1 for f in forecasts if f["level"] == "HIGH"),
            "medium": sum(1 for f in forecasts if f["level"] == "MEDIUM"),
            "low": sum(1 for f in forecasts if f["level"] == "LOW"),
        }
        return Response(
            {
                "data": {
                    "run_id": run_id,
                    "persisted": persist,
                    "count": len(forecasts),
                    "level_summary": summary,
                    "forecasts": forecasts,
                },
                "meta": {"success": True},
            }
        )
