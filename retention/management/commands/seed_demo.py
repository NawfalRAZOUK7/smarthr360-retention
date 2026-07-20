from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from retention.models import Action, AttritionForecast, Conversation, Employee, Signal


class Command(BaseCommand):
    help = "Seed coherent retention forecasts, conversations, and outcomes."

    @transaction.atomic
    def handle(self, *args, **options):
        people = (
            (4, "EMP-004", "Youssef Employee", "employee@demo.smarthr360.dev", 82, 86),
            (7, "EMP-007", "Yasmine Alaoui", "yasmine.alaoui@demo.smarthr360.dev", 63, 91),
            (8, "EMP-008", "Karim Bennis", "karim.bennis@demo.smarthr360.dev", 34, 79),
        )
        employees = {}
        for user_id, employee_id, name, email, engagement, performance in people:
            employees[user_id], _ = Employee.objects.update_or_create(user_id=user_id, defaults={"employee_id": employee_id, "name": name, "email": email, "engagement_score": engagement, "performance_score": performance, "absence_days_90d": 2 if user_id == 4 else 8})

        run_id = "00000000-0000-0000-0000-demo00000001"
        for user_id, risk, level in ((4, 18, "LOW"), (7, 57, "MEDIUM"), (8, 88, "CRITICAL")):
            AttritionForecast.objects.update_or_create(employee=employees[user_id], run_id=run_id, defaults={"risk_score": risk, "level": level, "factors": {"engagement": employees[user_id].engagement_score, "workload": risk}, "signal_trend_per_day": 0.8 if risk > 50 else -0.2, "top_drivers": ["Workload", "Engagement"], "rationale": "Deterministic coherent demo forecast."})

        for user_id, signal_type, intensity, need, retained in ((7, "low_engagement", 62, "career_growth", True), (8, "burnout_risk", 91, "workload_relief", False)):
            signal, _ = Signal.objects.update_or_create(employee=employees[user_id], signal_type=signal_type, defaults={"intensity": intensity, "resolved": retained})
            conversation, _ = Conversation.objects.update_or_create(employee=employees[user_id], signal=signal, defaults={"completed": True, "identified_need": need, "messages": [{"sender": "assistant", "text": "What support would make the biggest difference?"}, {"sender": "employee", "text": need.replace("_", " ").title()}]})
            Action.objects.update_or_create(conversation=conversation, employee=employees[user_id], description=f"Demo intervention: {need.replace('_', ' ')}", defaults={"priority": "critical" if intensity > 80 else "high", "status": "completed", "reviewed_at": timezone.now(), "reviewed_by_user_id": 2, "employee_retained": retained, "outcome_note": "Recorded demo outcome for ROI analytics.", "outcome_recorded_at": timezone.now(), "outcome_recorded_by_user_id": 2})
        self.stdout.write(self.style.SUCCESS("Retention demo data ready."))
