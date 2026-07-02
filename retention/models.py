"""Retention domain models (Module 5 — retention negotiator chatbot).

Rescued from the legacy `module-5` branch and aligned with platform
identity rules (ADR-005): the local Employee row references the auth
user by `user_id` value — no ForeignKey to another service.
"""

from django.db import models


class Employee(models.Model):
    """Employee engagement record (analytical store for detection)."""

    user_id = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True,
        help_text="smarthr360-auth user id (lets the employee chat about themselves).",
    )
    employee_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    engagement_score = models.IntegerField(default=100)   # 0-100
    performance_score = models.IntegerField(default=75)   # 0-100
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
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="signals")
    signal_type = models.CharField(max_length=50, choices=SIGNAL_TYPES)
    intensity = models.IntegerField()  # 0-100
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.signal_type} - {self.employee.name} ({self.intensity})"


class Conversation(models.Model):
    """Chatbot conversations with at-risk employees."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="conversations")
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, related_name="conversations")
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

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="actions")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="actions")
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_user_id = models.PositiveBigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.priority.upper()} - {self.employee.name}"
