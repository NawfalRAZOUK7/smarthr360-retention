from django.contrib import admin

from .models import (
    Action,
    AttritionForecast,
    AttritionRiskHistory,
    Conversation,
    Employee,
    Signal,
)

admin.site.register(Employee)
admin.site.register(Signal)
admin.site.register(Conversation)
admin.site.register(Action)


@admin.register(AttritionForecast)
class AttritionForecastAdmin(admin.ModelAdmin):
    list_display = ("employee", "risk_score", "level", "signal_trend_per_day", "generated_at")
    list_filter = ("level",)
    search_fields = ("employee__name", "employee__employee_id", "run_id")
    date_hierarchy = "generated_at"


@admin.register(AttritionRiskHistory)
class AttritionRiskHistoryAdmin(admin.ModelAdmin):
    list_display = ("employee_pk", "level", "version", "date_debut", "date_fin", "is_current")
    list_filter = ("level", "is_current")
