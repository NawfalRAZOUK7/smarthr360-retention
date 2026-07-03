"""Retention APIs (Module 5 — retention negotiator chatbot).

Flow (per the cahier des charges):
1. HR (or a scheduler) runs detection over the engagement store.
2. Detected signals open proactive chatbot conversations.
3. The at-risk employee replies; the bot identifies the primary need
   (LLM if configured, keyword fallback otherwise).
4. A retention action is generated and queued for HR review.
"""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action as drf_action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .models import Action, Conversation, Employee, Signal
from .serializers import (
    ActionSerializer,
    ConversationSerializer,
    EmployeeSerializer,
    SignalSerializer,
)
from . import notifications
from .services.actions import ActionGenerationService
from .services.chatbot import DialogueEngine, RetentionChatbotService
from .services.detection import RiskDetectionService


def _require_hr(request):
    if not has_hr_access(request.user):
        raise PermissionDenied("HR or Admin role required.")


class EmployeeViewSet(viewsets.ModelViewSet):
    """Engagement store management (HR)."""

    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        _require_hr(request)


class DetectRisksView(APIView):
    """POST /api/retention/detect/ — batch risk detection + auto-conversations."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        at_risk = RiskDetectionService.check_all_employees()
        results = []
        for item in at_risk:
            conversation = RetentionChatbotService.initiate_conversation(
                item["employee"], item["signal"]
            )
            notifications.notify_conversation_opened(item["employee"], conversation)
            results.append(
                {
                    "employee": EmployeeSerializer(item["employee"]).data,
                    "signal": SignalSerializer(item["signal"]).data,
                    "conversation_id": conversation.id,
                    "opening_message": conversation.messages[-1]["content"],
                }
            )
        return Response(
            {"at_risk_count": len(results), "results": results},
            status=status.HTTP_201_CREATED,
        )


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if has_hr_access(self.request.user):
            return Conversation.objects.all()
        # employees see only their own conversations (matched by user_id)
        return Conversation.objects.filter(employee__user_id=self.request.user.id)

    @drf_action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        """The employee replies. Multi-turn: the bot asks follow-up
        questions until it identifies the need; only then is the HR
        action generated and the signal resolved."""
        conversation = self.get_object()
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if conversation.completed:
            return Response(
                {"detail": "This conversation is already completed."},
                status=status.HTTP_409_CONFLICT,
            )

        is_owner = conversation.employee.user_id == request.user.id
        if not (is_owner or has_hr_access(request.user)):
            raise PermissionDenied("Not your conversation.")

        result = DialogueEngine.advance(conversation, message)

        action_data = None
        if result["completed"]:
            generated = ActionGenerationService.generate_action(conversation)
            conversation.signal.resolved = True
            conversation.signal.save(update_fields=["resolved"])
            notifications.notify_action_pending(generated)
            action_data = ActionSerializer(generated).data

        return Response(
            {
                "bot_reply": result["bot_reply"],
                "completed": result["completed"],
                "identified_need": result["identified_need"],
                "action": action_data,
                "messages": result["messages"],
            }
        )


class ActionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require_hr(self.request)
        qs = Action.objects.all()
        status_filter = self.request.query_params.get("status")
        return qs.filter(status=status_filter) if status_filter else qs

    @drf_action(detail=True, methods=["post"])
    def outcome(self, request, pk=None):
        """POST /actions/<id>/outcome/ {retained: bool, note?} — record
        whether the action actually kept the employee (HR)."""
        _require_hr(request)
        retained = request.data.get("retained")
        if not isinstance(retained, bool):
            return Response(
                {"detail": "retained must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        action_obj = self.get_object()
        if action_obj.status not in ("approved", "completed"):
            return Response(
                {"detail": "Outcome can only be recorded on approved or "
                           "completed actions."},
                status=status.HTTP_409_CONFLICT,
            )
        action_obj.employee_retained = retained
        action_obj.outcome_note = request.data.get("note", "")
        action_obj.outcome_recorded_at = timezone.now()
        action_obj.outcome_recorded_by_user_id = request.user.id
        action_obj.save(update_fields=[
            "employee_retained", "outcome_note", "outcome_recorded_at",
            "outcome_recorded_by_user_id",
        ])
        return Response(ActionSerializer(action_obj).data)

    @drf_action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """HR approves or rejects a proposed retention action."""
        _require_hr(request)
        decision = request.data.get("status")
        if decision not in ("approved", "rejected", "completed"):
            return Response(
                {"detail": "status must be approved, rejected or completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        action_obj = self.get_object()
        action_obj.status = decision
        action_obj.reviewed_at = timezone.now()
        action_obj.reviewed_by_user_id = request.user.id
        action_obj.save(
            update_fields=["status", "reviewed_at", "reviewed_by_user_id"]
        )
        return Response(ActionSerializer(action_obj).data)


class SignalListView(APIView):
    """GET /api/retention/signals/ — unresolved signals (HR)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        signals = Signal.objects.filter(resolved=False)
        return Response(SignalSerializer(signals, many=True).data)


class SignalIngestView(APIView):
    """POST /api/retention/signals/ingest/ — cross-service signal intake.

    Sibling services (e.g. workload's burnout alerts) push signals here
    with the ORIGINAL caller's token passed through: a user may report
    about themselves; managers/HR may report about anyone. Opens a
    proactive chatbot conversation, deduplicating on unresolved signals
    of the same type.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user_id = int(request.data.get("user_id") or 0)
            intensity = max(0, min(100, int(request.data.get("intensity", 50))))
        except (TypeError, ValueError):
            return Response(
                {"detail": "user_id and intensity must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        signal_type = request.data.get("signal_type")
        if not user_id or signal_type not in dict(Signal.SIGNAL_TYPES):
            return Response(
                {"detail": "valid user_id and signal_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_self = user_id == int(request.user.id)
        if not (is_self or has_hr_access(request.user)):
            from smarthr360_jwt_auth.access import has_manager_access

            if not has_manager_access(request.user):
                raise PermissionDenied(
                    "Only the employee themself or managers/HR may ingest signals."
                )

        employee, _ = Employee.objects.get_or_create(
            user_id=user_id,
            defaults={
                "employee_id": f"U-{user_id}",
                "name": (request.data.get("name")
                         or (getattr(request.user, "email", "") if is_self else "")
                         or f"user-{user_id}"),
                "email": (getattr(request.user, "email", "") if is_self else "")
                         or request.data.get("email", ""),
            },
        )

        existing = Signal.objects.filter(
            employee=employee, signal_type=signal_type, resolved=False
        ).first()
        if existing:
            return Response(
                {"detail": "unresolved signal of this type already open.",
                 "signal_id": existing.id, "deduplicated": True},
                status=status.HTTP_200_OK,
            )

        signal = Signal.objects.create(
            employee=employee, signal_type=signal_type, intensity=intensity
        )
        conversation = RetentionChatbotService.initiate_conversation(
            employee, signal
        )
        notifications.notify_conversation_opened(employee, conversation)
        return Response(
            {
                "signal_id": signal.id,
                "conversation_id": conversation.id,
                "opening_message": conversation.messages[-1]["content"],
                "source": request.data.get("source", "unknown"),
            },
            status=status.HTTP_201_CREATED,
        )


class OutcomeStatsView(APIView):
    """GET /api/retention/outcomes/ — retention effectiveness (HR).

    Success rate overall and per identified need — the numbers that
    prove (or disprove) that the chatbot's proposals work.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        actions = Action.objects.select_related("conversation")

        recorded = [a for a in actions if a.employee_retained is not None]
        retained = [a for a in recorded if a.employee_retained]

        by_need: dict[str, dict] = {}
        for action in recorded:
            need = action.conversation.identified_need or "general"
            bucket = by_need.setdefault(need, {"recorded": 0, "retained": 0})
            bucket["recorded"] += 1
            bucket["retained"] += int(bool(action.employee_retained))
        for bucket in by_need.values():
            bucket["success_rate"] = round(
                100 * bucket["retained"] / bucket["recorded"]
            )

        return Response(
            {
                "actions_total": actions.count(),
                "by_status": {
                    status_key: actions.filter(status=status_key).count()
                    for status_key, _ in Action.STATUS_CHOICES
                },
                "outcomes_recorded": len(recorded),
                "employees_retained": len(retained),
                "success_rate_percent": round(
                    100 * len(retained) / len(recorded)
                ) if recorded else None,
                "by_need": by_need,
            }
        )
