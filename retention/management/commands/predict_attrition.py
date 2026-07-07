"""Predict attrition risk for all employees and rank by risk.

    python manage.py predict_attrition [--no-persist] [--top 20]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from retention.services.attrition_service import AttritionEngine


class Command(BaseCommand):
    help = "Forward-looking attrition prediction, ranked by risk."

    def add_arguments(self, parser):
        parser.add_argument("--no-persist", action="store_true")
        parser.add_argument("--top", type=int, default=20)

    def handle(self, *args, **opts):
        run_id, forecasts = AttritionEngine().run(persist=not opts["no_persist"])
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"run {run_id}: {len(forecasts)} employee(s)")
        )
        for f in forecasts[: opts["top"]]:
            style = (
                self.style.ERROR
                if f["level"] in ("HIGH", "CRITICAL")
                else self.style.WARNING
                if f["level"] == "MEDIUM"
                else self.style.SUCCESS
            )
            drivers = ", ".join(f["top_drivers"][:2])
            self.stdout.write(
                style(
                    f"  [{f['level']:8}] {f['name'][:24]:24} "
                    f"risk={f['risk_score']:.0f} ({drivers})"
                )
            )
