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
from .services.actions import ActionGenerationService
from .services.chatbot import RetentionChatbotService
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
        """The employee replies; the bot extracts the need and an HR
        action is generated."""
        conversation = self.get_object()
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_owner = conversation.employee.user_id == request.user.id
        if not (is_owner or has_hr_access(request.user)):
            raise PermissionDenied("Not your conversation.")

        result = RetentionChatbotService.process_employee_response(
            conversation, message
        )
        generated = ActionGenerationService.generate_action(conversation)
        conversation.signal.resolved = True
        conversation.signal.save(update_fields=["resolved"])

        return Response(
            {
                "identified_need": result["identified_need"],
                "action": ActionSerializer(generated).data,
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
