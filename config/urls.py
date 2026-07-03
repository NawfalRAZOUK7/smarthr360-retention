"""URL configuration for the smarthr360-retention service."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def healthz(request):
    return JsonResponse({"status": "ok", "service": "smarthr360-retention"})


urlpatterns = [
    # Prometheus metrics (observability)
    path('', include('django_prometheus.urls')),
    path('admin/', admin.site.urls),
    path('healthz/', healthz, name='healthz'),

    # API documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Business APIs
    path('api/retention/', include('retention.urls')),
]
