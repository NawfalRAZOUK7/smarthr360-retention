from rest_framework import serializers

from .models import Action, Conversation, Employee, Signal


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id", "user_id", "employee_id", "name", "email",
            "engagement_score", "performance_score", "absence_days_90d",
            "last_evaluation_date",
        ]


class SignalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Signal
        fields = [
            "id", "employee", "employee_name", "signal_type",
            "intensity", "detected_at", "resolved",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id", "employee", "signal", "started_at", "completed",
            "identified_need", "messages",
        ]


class ActionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Action
        fields = [
            "id", "conversation", "employee", "employee_name", "description",
            "priority", "status", "created_at", "reviewed_at",
            "reviewed_by_user_id", "employee_retained", "outcome_note",
            "outcome_recorded_at",
        ]
        read_only_fields = [
            "conversation", "employee", "description", "priority",
            "created_at", "reviewed_at", "reviewed_by_user_id",
        ]
