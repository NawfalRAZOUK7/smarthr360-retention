from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    OutcomeStatsView,
    ActionViewSet,
    ConversationViewSet,
    DetectRisksView,
    EmployeeViewSet,
    SelfWellbeingCheckinView,
    SignalIngestView,
    SignalListView,
)
from .views_attrition import AttritionForecastView
from .views_export import AttritionExportView
from .views_roi import RetentionROIView

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="retention-employee")
router.register("conversations", ConversationViewSet, basename="retention-conversation")
router.register("actions", ActionViewSet, basename="retention-action")

urlpatterns = [
    path("detect/", DetectRisksView.as_view(), name="retention-detect"),
    path("signals/", SignalListView.as_view(), name="retention-signals"),
    path("outcomes/", OutcomeStatsView.as_view(), name="retention-outcomes"),
    path("attrition/", AttritionForecastView.as_view(), name="retention-attrition"),
    path("export/", AttritionExportView.as_view(), name="retention-export"),
    path("roi/", RetentionROIView.as_view(), name="retention-roi"),
    path("signals/ingest/", SignalIngestView.as_view(), name="retention-signal-ingest"),
    path("checkin/", SelfWellbeingCheckinView.as_view(), name="retention-self-checkin"),
    path("", include(router.urls)),
]
