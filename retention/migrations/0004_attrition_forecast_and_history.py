"""Attrition prediction (Phase 2): forecast store + SCD2 risk-band history."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retention", "0003_action_employee_retained_action_outcome_note_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttritionForecast",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("risk_score", models.FloatField()),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("CRITICAL", "Critical"),
                        ],
                        max_length=10,
                    ),
                ),
                ("factors", models.JSONField(default=dict)),
                ("signal_trend_per_day", models.FloatField(default=0.0)),
                ("top_drivers", models.JSONField(default=list)),
                ("rationale", models.TextField(blank=True)),
                ("run_id", models.CharField(db_index=True, max_length=36)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attrition_forecasts",
                        to="retention.employee",
                    ),
                ),
            ],
            options={"ordering": ["-generated_at", "-risk_score"]},
        ),
        migrations.CreateModel(
            name="AttritionRiskHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("date_debut", models.DateTimeField(db_index=True)),
                ("date_fin", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("is_current", models.BooleanField(default=True)),
                ("change_reason", models.CharField(blank=True, max_length=255)),
                ("changed_by_user_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("source_system", models.CharField(blank=True, max_length=32)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("employee_pk", models.PositiveBigIntegerField(db_index=True)),
                ("level", models.CharField(max_length=10)),
            ],
            options={"ordering": ["employee_pk", "-date_debut"]},
        ),
        migrations.AddIndex(
            model_name="attritionforecast",
            index=models.Index(
                fields=["employee", "-generated_at"], name="ret_attr_emp_gen_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="attritionforecast",
            index=models.Index(fields=["level"], name="ret_attr_level_idx"),
        ),
        migrations.AddIndex(
            model_name="attritionforecast",
            index=models.Index(fields=["run_id"], name="ret_attr_run_idx"),
        ),
        migrations.AddIndex(
            model_name="attritionriskhistory",
            index=models.Index(
                fields=["employee_pk", "is_current"], name="ret_attrhist_emp_curr_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="attritionriskhistory",
            constraint=models.UniqueConstraint(
                condition=models.Q(("date_fin__isnull", True)),
                fields=("employee_pk",),
                name="uniq_open_attrition_risk_per_employee",
            ),
        ),
        migrations.AddConstraint(
            model_name="attritionriskhistory",
            constraint=models.UniqueConstraint(
                fields=("employee_pk", "version"),
                name="uniq_attrition_risk_version",
            ),
        ),
    ]
