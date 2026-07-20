"""Tests for the attrition-risk CSV export (Phase 3)."""

from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import AttritionForecast, Employee
from .test_retention_flow import PUBLIC_PEM, bearer


class AttritionExportTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._s = override_settings(
            SMARTHR_JWT_AUTH={"PUBLIC_KEY": PUBLIC_PEM, "ISSUER": "smarthr360"}
        )
        cls._s.enable()
        conf.clear_cache()

    @classmethod
    def tearDownClass(cls):
        cls._s.disable()
        conf.clear_cache()
        super().tearDownClass()

    def setUp(self):
        self.emp = Employee.objects.create(
            employee_id="E-10", name="Rania Idrissi", email="r@corp.com",
            engagement_score=30, performance_score=60, absence_days_90d=8,
        )
        AttritionForecast.objects.create(
            employee=self.emp, risk_score=82.5, level=AttritionForecast.Level.HIGH,
            factors={}, signal_trend_per_day=0.2,
            top_drivers=["low_engagement", "high_absence"], rationale="test",
            run_id="run-1",
        )

    def test_export_csv_for_hr(self):
        resp = self.client.get("/api/retention/export/", **bearer(1, role="HR"))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("attachment", resp["Content-Disposition"])
        body = resp.content.decode()
        self.assertIn("employee_id,name,email,risk_score,level", body)
        self.assertIn("E-10", body)
        self.assertIn("HIGH", body)
        self.assertIn("low_engagement; high_absence", body)

    def test_export_forbidden_for_non_hr(self):
        self.assertEqual(
            self.client.get("/api/retention/export/", **bearer(9, role="EMPLOYEE")).status_code,
            403,
        )

    def test_export_requires_auth(self):
        self.assertEqual(self.client.get("/api/retention/export/").status_code, 401)
