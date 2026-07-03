from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionViewSet,
    ConversationViewSet,
    DetectRisksView,
    EmployeeViewSet,
    SignalIngestView,
    SignalListView,
)

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="retention-employee")
router.register("conversations", ConversationViewSet, basename="retention-conversation")
router.register("actions", ActionViewSet, basename="retention-action")

urlpatterns = [
    path("detect/", DetectRisksView.as_view(), name="retention-detect"),
    path("signals/", SignalListView.as_view(), name="retention-signals"),
    path("signals/ingest/", SignalIngestView.as_view(), name="retention-signal-ingest"),
    path("", include(router.urls)),
]
