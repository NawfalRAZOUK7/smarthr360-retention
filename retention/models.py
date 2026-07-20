"""Retention domain models (Module 5 — retention negotiator chatbot).

Rescued from the legacy `module-5` branch and aligned with platform
identity rules (ADR-005): the local Employee row references the auth
user by `user_id` value — no ForeignKey to another service.
"""

from django.db import models

from smarthr360_integration.history import SCD2HistoryBase


class Employee(models.Model):
    """Employee engagement record (analytical store for detection)."""

    user_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="smarthr360-auth user id (lets the employee chat about themselves).",
    )
    employee_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    engagement_score = models.IntegerField(default=100)  # 0-100
    performance_score = models.IntegerField(default=75)  # 0-100
    absence_days_90d = models.PositiveSmallIntegerField(default=0)
    last_evaluation_date = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.employee_id})"


class Signal(models.Model):
    """Risk signals detected for employees."""

    SIGNAL_TYPES = [
        ("low_engagement", "Low Engagement"),
        ("high_absence", "High Absence Rate"),
        ("poor_performance", "Poor Performance"),
        ("negative_feedback", "Negative Feedback"),
        # ingested from sibling services (e.g. smarthr360-workload)
        ("burnout_risk", "Burnout Risk (workload)"),
        # opt-in, non-anonymous self check-in (distinct from the anonymous
        # wellbeing surveys in core-hr)
        ("low_wellbeing", "Low Wellbeing (self check-in)"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="signals"
    )
    signal_type = models.CharField(max_length=50, choices=SIGNAL_TYPES)
    intensity = models.IntegerField()  # 0-100
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.signal_type} - {self.employee.name} ({self.intensity})"


class Conversation(models.Model):
    """Chatbot conversations with at-risk employees."""

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="conversations"
    )
    signal = models.ForeignKey(
        Signal, on_delete=models.CASCADE, related_name="conversations"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    identified_need = models.CharField(max_length=100, null=True, blank=True)
    messages = models.JSONField(default=list)

    def __str__(self):
        return f"Conversation with {self.employee.name} - {self.started_at}"


class Action(models.Model):
    """HR actions recommended by the system."""

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending HR Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="actions"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="actions"
    )
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_user_id = models.PositiveBigIntegerField(null=True, blank=True)

    # Outcome tracking: did the action actually retain the employee?
    # Recorded weeks/months after completion — this is what turns the
    # module into a measurable system (success-rate analytics).
    employee_retained = models.BooleanField(null=True, blank=True)
    outcome_note = models.TextField(blank=True)
    outcome_recorded_at = models.DateTimeField(null=True, blank=True)
    outcome_recorded_by_user_id = models.PositiveBigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.priority.upper()} - {self.employee.name}"


class AttritionForecast(models.Model):
    """A forward-looking attrition-risk prediction for an employee (Phase 2).

    Distinct from Signal (current detection): this is the *projected* risk of
    leaving, driven by the trajectory of signals + engagement/performance.
    Persisted so predictions can be tracked over time for BI.
    """

    class Level(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attrition_forecasts"
    )
    risk_score = models.FloatField()  # 0..100
    level = models.CharField(max_length=10, choices=Level.choices)
    factors = models.JSONField(default=dict)
    signal_trend_per_day = models.FloatField(default=0.0)
    top_drivers = models.JSONField(default=list)
    rationale = models.TextField(blank=True)

    run_id = models.CharField(max_length=36, db_index=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at", "-risk_score"]
        indexes = [
            models.Index(
                fields=["employee", "-generated_at"], name="ret_attr_emp_gen_idx"
            ),
            models.Index(fields=["level"], name="ret_attr_level_idx"),
            models.Index(fields=["run_id"], name="ret_attr_run_idx"),
        ]

    def __str__(self):
        return f"{self.employee.name}: {self.risk_score:.0f} ({self.level})"


class AttritionRiskHistory(SCD2HistoryBase):
    """SCD Type 2 timeline of an employee's attrition-risk *band* (shared base).

    Tracks how long an employee stays at LOW/MEDIUM/HIGH/CRITICAL — the dwell
    time HR cares about. No SCD2 logic re-implemented (smarthr360-integration).
    """

    employee_pk = models.PositiveBigIntegerField(db_index=True)
    level = models.CharField(max_length=10)

    SCD2_OWNER_FIELDS = ("employee_pk",)

    class Meta:
        ordering = ["employee_pk", "-date_debut"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee_pk"],
                condition=models.Q(date_fin__isnull=True),
                name="uniq_open_attrition_risk_per_employee",
            ),
            models.UniqueConstraint(
                fields=["employee_pk", "version"],
                name="uniq_attrition_risk_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=["employee_pk", "is_current"], name="ret_attrhist_emp_curr_idx"
            )
        ]

    @property
    def tracked_snapshot(self) -> dict:
        return {"level": self.level}
