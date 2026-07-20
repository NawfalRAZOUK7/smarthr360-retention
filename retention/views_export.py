"""CSV export of the latest attrition-risk forecast (HR).

Streams the most recent detection run — one row per employee with risk score,
level and the key drivers — so HR can share or archive a retention snapshot.
"""

import csv
from datetime import date

from django.http import HttpResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .models import AttritionForecast


class AttritionExportView(APIView):
    """GET /api/retention/export/ — latest attrition forecast as CSV."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_hr_access(request.user):
            raise PermissionDenied("HR or Admin role required.")

        latest = AttritionForecast.objects.order_by("-generated_at").first()
        forecasts = (
            AttritionForecast.objects.filter(run_id=latest.run_id)
            .select_related("employee")
            .order_by("-risk_score")
            if latest
            else []
        )

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="attrition_report_{date.today().isoformat()}.csv"'
        )
        writer = csv.writer(resp)
        writer.writerow(
            [
                "employee_id",
                "name",
                "email",
                "risk_score",
                "level",
                "engagement_score",
                "performance_score",
                "absence_days_90d",
                "signal_trend_per_day",
                "top_drivers",
                "generated_at",
            ]
        )
        for f in forecasts:
            emp = f.employee
            drivers = f.top_drivers if isinstance(f.top_drivers, list) else []
            writer.writerow(
                [
                    emp.employee_id,
                    emp.name,
                    emp.email,
                    round(f.risk_score, 1),
                    f.level,
                    emp.engagement_score,
                    emp.performance_score,
                    emp.absence_days_90d,
                    round(f.signal_trend_per_day, 3),
                    "; ".join(str(d) for d in drivers),
                    f.generated_at.isoformat(),
                ]
            )
        return resp
